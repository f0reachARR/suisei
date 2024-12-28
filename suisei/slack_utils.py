import re
from datetime import datetime
from typing import Tuple

import aiohttp
from pytz import timezone
from slack_bolt import BoltContext

from .env import SLACK_BOT_TOKEN

EMOJI_PATTERN = re.compile(r":[\w_-]+:")


def remove_unused_element(context: BoltContext, text: str) -> str:
    text = text.replace(f"<@{context.bot_user_id}>", "")
    # text = EMOJI_PATTERN.sub("", text)
    return text.strip()


def is_this_app_mentioned(context: BoltContext, text: str) -> bool:
    return f"<@{context.bot_user_id}>" in text


async def download_slack_image_content(image_url: str) -> Tuple[str, bytes]:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            image_url,
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        ) as response:
            if response.status != 200:
                error = (
                    f"Request to {image_url} failed with status code {response.status}"
                )
                raise FileNotFoundError(error, response)

            content_type = response.headers["content-type"]
            if content_type.startswith("text/html"):
                error = (
                    f"You don't have the permission to download this file: {image_url}"
                )
                raise FileNotFoundError(error, response)

            if image_url.endswith(".pdf"):
                content_type = "application/pdf"

            if image_url.endswith(".csv"):
                content_type = "text/plain"

            if (
                not content_type.startswith("image/")
                and not content_type.startswith("application/pdf")
                and not content_type.startswith("text/")
            ):
                error = (
                    f"The responded content-type is not for image data: {content_type}"
                )
                raise FileNotFoundError(error, response)

            return (content_type, await response.read())


def parse_ts(ts: str) -> datetime:
    unix = ts.split(".")[0]
    return timezone("Asia/Tokyo").localize(datetime.fromtimestamp(int(unix)))
