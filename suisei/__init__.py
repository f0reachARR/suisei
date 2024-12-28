import logging
from typing import Callable

from slack_bolt import Ack, BoltContext
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient as WebClient
from slack_sdk.http_retry.builtin_async_handlers import AsyncRateLimitErrorRetryHandler

from .bolt_listeners import respond_to_app_mention, respond_to_message
from .env import SLACK_APP_LOG_LEVEL, SLACK_APP_TOKEN, SLACK_BOT_TOKEN


async def set_locale(
    context: BoltContext,
    client: WebClient,
    next_: Callable,
):
    user_id = context.actor_user_id or context.user_id
    user_info = await client.users_info(user=user_id, include_locale=True)
    context["locale"] = user_info.get("user", {}).get("locale")
    await next_()


async def just_ack(ack: Ack):
    await ack()


async def main():
    logging.basicConfig(level=SLACK_APP_LOG_LEVEL)

    app = AsyncApp(
        token=SLACK_BOT_TOKEN,
        process_before_response=False,
    )

    app.client.retry_handlers.append(AsyncRateLimitErrorRetryHandler(max_retry_count=2))
    app.middleware(set_locale)

    app.event("app_mention")(ack=just_ack, lazy=[respond_to_app_mention])
    app.event("message")(ack=just_ack, lazy=[respond_to_message])

    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    await handler.start_async()
