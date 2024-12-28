from base64 import b64encode

from slack_bolt import BoltContext
from google.genai.types import Content, Part, Blob

from .env import GEMINI_FILE_MAX_SIZE
from .llm_utils import datetime_to_string
from .slack_utils import download_slack_image_content, parse_ts, remove_unused_element


# SlackのmessageをLLM向けのdictに変換する
def create_chat(context: BoltContext, message: dict) -> Content | None:
    user_id: str = message["user"]
    text: str = message["text"]
    ts = parse_ts(message["ts"])
    dt = datetime_to_string(ts)

    if user_id == context.bot_user_id:
        return Content(role="model", parts=[Part(text=text)])

    else:
        text = remove_unused_element(context, text)
        files: list[dict] = message.get("files", [])

        if text == "" and len(files) == 0:
            return None

        content = Content(role="user", parts=[])

        if text != "":
            content.parts.append(Part(text=f"<@{user_id}> {dt} {text}"))

        if len(files) > 0:
            for file in files:
                type, file = download_slack_image_content(file["url_private"])

                if len(file) > GEMINI_FILE_MAX_SIZE and GEMINI_FILE_MAX_SIZE != -1:
                    raise ValueError(f"File size is too large: {len(file)}")

                content.parts.append(
                    Part(
                        inline_data=Blob(
                            data=file,
                            mime_type=type,
                        )
                    )
                )

        return content
