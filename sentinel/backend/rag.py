from typing import Any, Dict

class LlamaIndexPipeline:
    def __init__(self, index_path: str, config: Dict[str, Any] | None = None):
        self.index_path = index_path
        self.config = config or {}

    def query(self, text: str) -> str:
        return f"RAG query received: {text}"
