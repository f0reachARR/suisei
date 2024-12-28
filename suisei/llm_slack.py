from base64 import b64encode

from slack_bolt import BoltContext

from .env import LITELLM_FILE_MAX_SIZE
from .llm_utils import datetime_to_string
from .slack_utils import download_slack_image_content, parse_ts, remove_unused_element


# SlackのmessageをLLM向けのdictに変換する
def create_chat(context: BoltContext, message: dict) -> dict | None:
    user_id: str = message["user"]
    text: str = message["text"]
    ts = parse_ts(message["ts"])
    dt = datetime_to_string(ts)

    if user_id == context.bot_user_id:
        return {
            "role": "assistant",
            "content": text,
        }

    else:
        text = remove_unused_element(context, text)
        files: list[dict] = message.get("files", [])

        if text == "" and len(files) == 0:
            return None

        contents = []

        if text != "":
            contents.append(
                {
                    "type": "text",
                    "text": f"<@{user_id}> {dt} {text}",
                }
            )

        if len(files) > 0:
            for file in files:
                type, file = download_slack_image_content(file["url_private"])

                if len(file) > LITELLM_FILE_MAX_SIZE and LITELLM_FILE_MAX_SIZE != -1:
                    raise ValueError(f"File size is too large: {len(file)}")

                encoded_file = b64encode(file).decode("utf-8")
                encoded_file_with_type = f"data:{type};base64,{encoded_file}"

                contents.append(
                    {
                        "type": "image_url",
                        "image_url": encoded_file_with_type,
                    }
                )

        return {
            "role": "user",
            "content": contents,
        }
