from datetime import datetime

from pytz import timezone
from slack_bolt import BoltContext
from google.genai.types import Content, Part

from .env import SYSTEM_TEXT


def build_system_prompt(context: BoltContext) -> Content:
    ts = timezone("Asia/Tokyo").localize(datetime.now())
    text = SYSTEM_TEXT.format(
        bot_user_id=context.bot_user_id, current_time=datetime_to_string(ts)
    )

    return Content(role="user", parts=[Part(text=text)])


def datetime_to_string(dt: datetime) -> str:
    return datetime.strftime(dt, "%Y/%m/%d %H:%M:%S")
