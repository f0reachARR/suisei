import logging
import re
import time
from typing import List

import litellm
from slack_bolt import BoltContext
from slack_sdk import WebClient

from .tools.google import create_google_tools_if_available
from .env import (
    GEMINI_SAFETY_SETTINGS,
    LITELLM_MAX_TOKENS,
    LITELLM_MODEL,
    LITELLM_TEMPERATURE,
    LITELLM_TIMEOUT_SECONDS,
)
from .llm_slack import create_chat
from .llm_utils import build_system_prompt
from .slack_format import format_assistant_reply


# ツール等に対応するため再帰できるように関数を切り出す
def _model_streamer(
    client: WebClient,
    logger: logging.Logger,
    channel: str,
    thread_ts: str,
    messages: List[dict],
):
    tools = create_google_tools_if_available(LITELLM_MODEL)
    response = litellm.completion(
        messages=messages,
        timeout_seconds=LITELLM_TIMEOUT_SECONDS,
        model=LITELLM_MODEL,
        max_tokens=LITELLM_MAX_TOKENS,
        temperature=LITELLM_TEMPERATURE,
        stream=True,
        safety_settings=GEMINI_SAFETY_SETTINGS,
        tools=tools,
    )

    # 長過ぎるメッセージはSlackが受け付けないため、分割して投稿する
    # streamなので、だんだん投稿される感じになる
    chunks = []
    buffer: List[str] = []
    remain_message = ""
    complete_message = ""
    is_same_message = False
    same_message: List[str] = []

    def flush(is_finished: bool = False):
        nonlocal buffer
        nonlocal client
        nonlocal channel
        nonlocal thread_ts

        # bufferを投稿していく
        while len(buffer) > 0:
            idx = 1
            text_plus1 = ""
            enforce_send = False
            while idx < len(buffer) - 1:
                text_plus1 = "\n".join(buffer[: idx + 1])
                if buffer[idx] != "---" and buffer[idx + 1] == "---":
                    enforce_send = True
                    break
                if len(text_plus1) > 1024:
                    break
                idx += 1

            text = "\n".join(filter(lambda x: x != "---", buffer[:idx]))

            print(buffer)

            # 全部足しても1024文字以下なら保留・終了理由がある場合は投稿
            if (
                len(text_plus1) <= 1024
                and len(text) < 1024
                and not is_finished
                and not enforce_send
            ):
                break

            text = format_assistant_reply(text)

            if len(text) > 0:
                logger.debug(f"Post message: {text} ({len(text)})")

                client.chat_postMessage(
                    channel=channel,
                    text=text,
                    thread_ts=thread_ts,
                )

                time.sleep(1)  # 連続投稿を避けるために1秒待つ

            buffer = buffer[idx:]

    INLINE_CODEBLOCK_RE = re.compile(r"(.+)```")
    for chunk in response:
        chunks.append(chunk)

        item = chunk.choices[0]

        delta: str | None = item.get("delta", {}).get("content")
        if delta is not None:
            complete_message += delta
            # 最後の\nまでのメッセージを分割してbufferに追加
            idx = delta.rfind("\n")
            if idx == -1:
                remain_message += delta
            else:
                part = remain_message + delta[: idx + 1]

                # 行の途中で出てきたコードブロックは改行させる
                if INLINE_CODEBLOCK_RE.match(part):
                    part = INLINE_CODEBLOCK_RE.sub(r"\1\n```", part)

                for line in part.split("\n"):
                    line = line.rstrip("\n ")
                    if not is_same_message and line.startswith("```"):
                        is_same_message = True
                        same_message.clear()
                        same_message.append(line)
                    elif is_same_message:
                        same_message.append(line)
                        if line.find("```") != -1:
                            is_same_message = False
                            buffer.append("\n".join(same_message))
                    else:
                        buffer.append(line)
                remain_message = delta[idx + 1 :]
        # メッセージが終了している場合は終了
        if item.get("finish_reason") is not None:
            logger.info(f"Finish reason: {item['finish_reason']}")
            break

        flush(item.get("finish_reason") is not None)

    # 最後のメッセージを処理
    if is_same_message:
        buffer.append("\n".join(same_message))

    if len(remain_message) > 0:
        for line in remain_message.split("\n"):
            buffer.append(line)

    llm_response = litellm.stream_chunk_builder(chunks, messages=messages)

    logger.debug(f"Complete message: {llm_response.model_dump_json()}")

    # 最後のメッセージを投稿
    flush(True)


def start_model_streamer(
    context: BoltContext,
    client: WebClient,
    logger: logging.Logger,
    channel: str,
    thread_ts: str,
    messages: List[dict],
):
    llm_messages = [create_chat(context, message) for message in messages]

    if llm_messages[-1] is None:
        # メッセージが取得できなかった場合は反応しない
        return

    llm_messages: List[dict] = list(filter(lambda x: x is not None, llm_messages))

    if len(llm_messages) == 0:
        raise ValueError("No messages to send to LLM")

    llm_messages = [
        {
            "role": "system",
            "content": build_system_prompt(context),
        }
    ] + llm_messages

    _model_streamer(
        client=client,
        context=context,
        logger=logger,
        channel=channel,
        thread_ts=thread_ts,
        messages=llm_messages,
    )
