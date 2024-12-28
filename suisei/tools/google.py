from typing import List


def create_google_tools_if_available(model: str) -> List[dict]:
    if model.startswith("gemini/gemini-"):
        return [{"googleSearch": {}}]
    return []
