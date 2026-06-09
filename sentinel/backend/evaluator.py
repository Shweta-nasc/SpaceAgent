from typing import List

class EvaluationHarness:
    def __init__(self, metrics: List[str] | None = None):
        self.metrics = metrics or ["accuracy", "latency", "coverage"]

    def run(self, results: List[dict]) -> dict:
        return {
            "count": len(results),
            "metrics": self.metrics,
            "summary": "Evaluation harness placeholder",
        }
