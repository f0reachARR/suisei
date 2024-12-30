import os

from dotenv import load_dotenv

load_dotenv(override=True)

DEFAULT_SYSTEM_TEXT = ""
SYSTEM_TEXT = os.environ.get("GEMINI_SYSTEM_TEXT", DEFAULT_SYSTEM_TEXT)

assert SYSTEM_TEXT != ""

# LITELLM_TIMEOUT_SECONDS = int(os.environ.get("LITELLM_TIMEOUT_SECONDS", "30"))
# LITELLM_MODEL = os.environ.get("LITELLM_MODEL", "gemini/gemini-2.0-flash-exp")
# LITELLM_TEMPERATURE = float(os.environ.get("LITELLM_TEMPERATURE", "1"))
# LITELLM_MAX_TOKENS = int(os.environ.get("LITELLM_MAX_TOKENS", "8192"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MAX_TOKENS = int(os.environ.get("GEMINI_MAX_TOKENS", "8192"))
GEMINI_TEMPERATURE = float(os.environ.get("GEMINI_TEMPERATURE", "1"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp")
GEMINI_FILE_MAX_SIZE = int(os.environ.get("GEMINI_FILE_MAX_SIZE", "-1"))

assert GEMINI_API_KEY is not None

SLACK_APP_LOG_LEVEL = os.environ.get("SLACK_APP_LOG_LEVEL", "INFO")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

GEMINI_SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_LOW_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_LOW_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_LOW_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_LOW_AND_ABOVE",
    },
]
