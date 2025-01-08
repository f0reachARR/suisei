from json import loads
import logging
import re
import time
from typing import List

from slack_bolt import BoltContext
from slack_sdk import WebClient
from google.genai import Client
from google.genai.types import (
    GenerateContentConfig,
    Content,
    Tool,
    GoogleSearch,
    GroundingChunk,
)

from .slack_markdown.chunker import SlackChunker
from .env import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MAX_TOKENS,
    GEMINI_TEMPERATURE,
)
from .llm_slack import create_chat
from .llm_utils import build_system_prompt
from .conversation_store import ConversationStore

gemini = Client(api_key=GEMINI_API_KEY)
store = ConversationStore()


# ツール等に対応するため再帰できるように関数を切り出す
def _model_streamer(
    context: BoltContext,
    client: WebClient,
    logger: logging.Logger,
    channel: str,
    thread_ts: str,
    messages: List[Content],
):
    response = gemini.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=messages,
        config=GenerateContentConfig(
            temperature=GEMINI_TEMPERATURE,
            max_output_tokens=GEMINI_MAX_TOKENS,
            system_instruction=build_system_prompt(context),
            tools=[
                Tool(
                    google_search=GoogleSearch(),
                ),
            ],
        ),
    )

    # 長過ぎるメッセージはSlackが受け付けないため、分割して投稿する
    # streamなので、だんだん投稿される感じになる
    grounding_chunks: List[GroundingChunk] = []
    chunker = SlackChunker(
        client=client,
        channel=channel,
        thread_ts=thread_ts,
    )

    def flush():
        nonlocal chunker

        while True:
            result = chunker.consume()
            if result is None:
                break

            time.sleep(1)  # 連続投稿を避けるために1秒待つ

    for chunk in response:
        messages.append(chunk.candidates[0].content)

        item = chunk.candidates[0].content.parts[0]

        if (
            chunk.candidates[0].grounding_metadata is not None
            and chunk.candidates[0].grounding_metadata.grounding_chunks is not None
        ):
            grounding_chunks.extend(
                chunk.candidates[0].grounding_metadata.grounding_chunks
            )

        delta_content: str | None = item.text
        if delta_content is not None:
            chunker.feed(delta_content)
            flush()

        delta_tool = item.function_call
        if delta_tool is not None:
            for tool in delta_tool:
                print(tool)

        # メッセージが終了している場合は終了
        finish_reason = chunk.candidates[0].finish_reason
        is_finished = finish_reason is not None

        if is_finished:
            logger.info(f"Finish reason: {finish_reason}")
            break

    # 最後のメッセージを投稿
    print(chunker.finish())
    flush()

    try:
        grounding_urls = []
        for grounding_chunk in grounding_chunks:
            grounding_urls.append(
                f"<{grounding_chunk.web.uri}|{grounding_chunk.web.title}>"
            )
        if len(grounding_urls) > 0:
            client.chat_postMessage(
                channel=channel,
                text=f"Grounding: {' '.join(grounding_urls)}",
                thread_ts=thread_ts,
            )
    except Exception as e:
        logger.error(f"Failed to get grounding: {e}")

    store.set(channel, thread_ts, messages)


def start_model_streamer(
    context: BoltContext,
    client: WebClient,
    logger: logging.Logger,
    channel: str,
    thread_ts: str,
    messages: List[dict],
):
    stored_messages = store.get(channel, thread_ts)
    if stored_messages is None:
        llm_messages = [create_chat(context, message) for message in messages]

    else:
        llm_messages = stored_messages
        llm_messages.append(
            create_chat(context, messages[-1])
        )  # 最後のメッセージを追加

    if llm_messages[-1] is None:
        # メッセージが取得できなかった場合は反応しない
        return

    llm_messages: List[Content] = list(filter(lambda x: x is not None, llm_messages))

    print(llm_messages)

    if len(llm_messages) == 0:
        raise ValueError("No messages to send to LLM")

    _model_streamer(
        client=client,
        context=context,
        logger=logger,
        channel=channel,
        thread_ts=thread_ts,
        messages=llm_messages,
    )
