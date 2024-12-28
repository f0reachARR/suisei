import logging
import traceback
from typing import Literal, Union

from slack_bolt import BoltContext
from slack_sdk.web.async_client import AsyncWebClient as WebClient

from .llm_slack_executor import start_model_streamer
from .slack_utils import is_this_app_mentioned, remove_unused_element


async def _responder(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
    type: Union[Literal["mention"], Literal["message"]],
):
    thread_ts: str | None = payload.get("thread_ts")
    text: str = payload["text"]
    channel: str = payload["channel"]
    user: str = payload["user"]
    ts: str = payload["ts"]
    cleaned_text = remove_unused_element(context, text)

    print(payload)

    # 自分は無視
    if user == context.bot_user_id:
        return

    # メンションで内容がない場合は無視
    if type == "mention" and cleaned_text == "":
        return

    # メンションでない場合で、自分が言及されていたらメンションのハンドラーと重複するため無視
    if type != "mention" and is_this_app_mentioned(context, text):
        return

    if type == "message" and thread_ts is None:
        # メッセージの場合、メンションがなければ無視
        if not is_this_app_mentioned(context, text):
            return

    messages = []

    # スレッド内であれば過去の履歴を取得してLLMに渡す
    if thread_ts is not None:
        history = await client.conversations_replies(
            channel=channel,
            ts=thread_ts,
        )

        # 全件取得できていない場合はエラーを返す
        if history["has_more"]:
            await client.chat_postMessage(
                channel=channel,
                text="スレッドが長すぎます",
                thread_ts=thread_ts,
            )
            return

        # メンションでない場合、過去に自分がメンションされている・自分が発言しているメッセージを確認する
        if type == "message":
            has_mentioned = any(
                is_this_app_mentioned(context, message["text"])
                for message in history["messages"]
            ) or any(
                message["user"] == context.bot_user_id
                for message in history["messages"]
            )

            # 見つからなければ関係ないスレッドなので無視
            if not has_mentioned:
                return

            has_abort = any(
                message["user"] != context.bot_user_id
                and message["text"].strip() == "abort"
                for message in history["messages"]
            ) or any(
                message["user"] == context.bot_user_id
                and message.get("meta", {}).get("suichan_type") == "abort"
                for message in history["messages"]
            )

            # abortがあれば無視
            if has_abort:
                return

        # 過去のメッセージを投入する
        for message in history["messages"]:
            # ただしトリガーのメッセージは無視
            if message["ts"] == ts:
                continue

            messages.append(message)

    messages.append(payload)

    logger.info(f"Input {len(messages)} messages")

    await start_model_streamer(
        context=context,
        client=client,
        logger=logger,
        channel=channel,
        thread_ts=thread_ts if thread_ts is not None else ts,
        messages=messages,
    )


async def respond_to_app_mention(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    try:
        await _responder(
            context=context,
            payload=payload,
            client=client,
            logger=logger,
            type="mention",
        )
    except Exception as e:
        ex = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(ex)
        await client.chat_postMessage(
            channel=payload["channel"],
            text=f"エラーが発生しました\n{ex}",
            thread_ts=payload["ts"],
        )


async def respond_to_message(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    if payload.get("subtype") in ["message_changed", "message_deleted"]:
        return

    try:
        await _responder(
            context=context,
            payload=payload,
            client=client,
            logger=logger,
            type="message",
        )
    except Exception as e:
        ex = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(ex)
        await client.chat_postMessage(
            channel=payload["channel"],
            text=f"エラーが発生しました\n{ex}",
            thread_ts=payload["ts"],
        )
