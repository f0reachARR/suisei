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
    GenerateContentResponse,
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

gemini = Client(api_key=GEMINI_API_KEY)


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
    chunks: List[GenerateContentResponse] = []
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
        chunks.append(chunk)

        item = chunk.candidates[0].content.parts[0]

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

    # print(chunks)

    try:
        grounding = chunks[-1].candidates[0].grounding_metadata.grounding_chunks
        grounding_urls = []
        for grounding_chunk in grounding:
            grounding_urls.append(
                f"<{grounding_chunk.web.uri}|{grounding_chunk.web.title}>"
            )
        client.chat_postMessage(
            channel=channel,
            text=f"Grounding: {''.join(grounding_urls)}",
            thread_ts=thread_ts,
        )
    except Exception as e:
        logger.error(f"Failed to get grounding: {e}")


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

    llm_messages: List[Content] = list(filter(lambda x: x is not None, llm_messages))

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
