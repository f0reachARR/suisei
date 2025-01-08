from typing import List
from valkey import Valkey
from google.genai.types import Content
import pickle

from .env import VALKEY_DB, VALKEY_HOST, VALKEY_PORT


class ConversationStore:
    def __init__(self):
        self._valkey = Valkey(host=VALKEY_HOST, port=VALKEY_PORT, db=VALKEY_DB)

    def get(self, channel: str, thread_ts: str) -> List[Content] | None:
        value = self._valkey.get(f"cv:{channel}-{thread_ts}")

        if value is None:
            return None

        decoded = pickle.loads(value)

        if not isinstance(decoded, list) or not all(
            isinstance(x, Content) for x in decoded
        ):
            raise ValueError(f"Stored value is not valid")

        return decoded

    def set(self, channel: str, thread_ts: str, messages: List[Content]):
        self._valkey.set(f"cv:{channel}-{thread_ts}", pickle.dumps(messages))
