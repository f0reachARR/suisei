import asyncio
from json import loads
import logging
import re
import time
from typing import List

import litellm
from slack_bolt import BoltContext
from slack_sdk.web.async_client import AsyncWebClient as WebClient
from google.genai import Client
from google.genai.types import (
    GenerateContentConfig,
    Content,
    Tool,
    GoogleSearch,
    ToolCodeExecution,
    GenerateContentResponse,
    LiveConnectConfig,
    GenerationConfig,
    LiveClientContent,
    FunctionDeclaration,
    LiveClientToolResponse,
    FunctionResponse,
)
from google.genai.live import AsyncSession

from .env import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MAX_TOKENS,
    GEMINI_TEMPERATURE,
)
from .llm_slack import create_chat
from .llm_utils import build_system_prompt
from .slack_format import format_assistant_reply

gemini = Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1alpha"})


def get_current_weather(
    location: str,
) -> int:
    """Returns the current weather.

    Args:
      location: The city and state, e.g. San Francisco, CA
    """
    return "sunny"


INLINE_CODEBLOCK_RE = re.compile(r"(.+)```")


# ツール等に対応するため再帰できるように関数を切り出す
async def _model_streamer(
    context: BoltContext,
    client: WebClient,
    logger: logging.Logger,
    channel: str,
    thread_ts: str,
    messages: List[Content],
):
    config = LiveConnectConfig(
        system_instruction=build_system_prompt(context),
        tools=[
            Tool(google_search=GoogleSearch()),
            Tool(code_execution=ToolCodeExecution()),
            Tool(
                function_declarations=[
                    FunctionDeclaration.from_function(gemini, get_current_weather)
                ]
            ),
        ],
        response_modalities=["TEXT"],
        generation_config=GenerationConfig(
            temperature=GEMINI_TEMPERATURE,
            max_output_tokens=GEMINI_MAX_TOKENS,
        ),
    )
    live_input = LiveClientContent(turns=messages, turn_complete=True)

    buffer: List[str] = []
    remain_message = ""
    complete_message = ""
    is_same_message = False
    same_message: List[str] = []

    async def flush(is_finished: bool = False):
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

                await client.chat_postMessage(
                    channel=channel,
                    text=text,
                    thread_ts=thread_ts,
                )

                await asyncio.sleep(1)  # 連続投稿を避けるために1秒待つ

            buffer = buffer[idx:]

    # 長過ぎるメッセージはSlackが受け付けないため、分割して投稿する
    # streamなので、だんだん投稿される感じになる
    async with gemini.aio.live.connect(model=GEMINI_MODEL, config=config) as session:
        session: AsyncSession = session
        await session.send(live_input)
        async for response in session.receive():
            print(response)

            has_item = (
                response.server_content is not None
                and response.server_content.model_turn is not None
                and response.server_content.model_turn.parts is not None
                and len(response.server_content.model_turn.parts) > 0
            )
            turn = response.server_content.model_turn.parts[0] if has_item else None
            is_finished = (
                response.server_content.turn_complete
                if response.server_content is not None
                else False
            )

            if has_item and turn.text is not None:
                delta_content = turn.text
                complete_message += delta_content
                # 最後の\nまでのメッセージを分割してbufferに追加
                idx = delta_content.rfind("\n")
                if idx == -1:
                    remain_message += delta_content
                else:
                    part = remain_message + delta_content[: idx + 1]

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
                    remain_message = delta_content[idx + 1 :]

            if response.tool_call is not None:
                function_calls = response.tool_call.function_calls
                function_calls = function_calls if function_calls is not None else []

                for function_call in function_calls:
                    if function_call.name == "get_current_weather":
                        weather = get_current_weather(**function_call.args)
                        await session.send(
                            LiveClientToolResponse(
                                function_responses=[
                                    FunctionResponse(
                                        id=function_call.id,
                                        name=function_call.name,
                                        response={"output": weather},
                                    )
                                ]
                            )
                        )

            # メッセージが終了している場合は終了
            await flush(is_finished)

            if is_finished:
                logger.info(f"Finished")
                break

    # 最後のメッセージを処理
    if is_same_message:
        buffer.append("\n".join(same_message))

    if len(remain_message) > 0:
        for line in remain_message.split("\n"):
            buffer.append(line)

    # 最後のメッセージを投稿
    await flush(True)


async def start_model_streamer(
    context: BoltContext,
    client: WebClient,
    logger: logging.Logger,
    channel: str,
    thread_ts: str,
    messages: List[dict],
):
    llm_messages = [await create_chat(context, message) for message in messages]

    if llm_messages[-1] is None:
        # メッセージが取得できなかった場合は反応しない
        return

    llm_messages: List[Content] = list(filter(lambda x: x is not None, llm_messages))

    if len(llm_messages) == 0:
        raise ValueError("No messages to send to LLM")

    await _model_streamer(
        client=client,
        context=context,
        logger=logger,
        channel=channel,
        thread_ts=thread_ts,
        messages=llm_messages,
    )
