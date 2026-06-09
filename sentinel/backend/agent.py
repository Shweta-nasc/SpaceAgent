from typing import Any, Dict

class LangGraphAgent:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    def run(self, prompt: str) -> str:
        return f"LangGraphAgent received prompt: {prompt}"
