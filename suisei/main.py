import logging
from typing import Callable

from slack_bolt import Ack, App, BoltContext
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

from .bolt_listeners import respond_to_app_mention, respond_to_message
from .env import SLACK_APP_LOG_LEVEL, SLACK_APP_TOKEN, SLACK_BOT_TOKEN


def set_locale(
    context: BoltContext,
    client: WebClient,
    next_: Callable,
):
    user_id = context.actor_user_id or context.user_id
    user_info = client.users_info(user=user_id, include_locale=True)
    context["locale"] = user_info.get("user", {}).get("locale")
    next_()


def just_ack(ack: Ack):
    ack()


def main():
    logging.basicConfig(level=SLACK_APP_LOG_LEVEL)

    app = App(
        token=SLACK_BOT_TOKEN,
        process_before_response=False,
    )

    app.client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=2))
    app.middleware(set_locale)

    app.event("app_mention")(ack=just_ack, lazy=[respond_to_app_mention])
    app.event("message")(ack=just_ack, lazy=[respond_to_message])

    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
