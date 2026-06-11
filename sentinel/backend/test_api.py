import json
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os

# Adjust sys.path to ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from models import SentinelOutput, SSEEventType

class TestSentinelAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_get_scenarios(self):
        response = self.client.get("/scenarios")
        self.assertEqual(response.status_code, 200)
        scenarios = response.json()
        self.assertEqual(len(scenarios), 3)
        for s in scenarios:
            self.assertIn("scenario_id", s)
            self.assertIn("fault_type", s)
            self.assertIn("pre_fault_telemetry", s)

    @patch("agent.SentinelAgent._call_llm")
    def test_analyze_streaming(self, mock_call_llm):
        # Mock LLM response JSON that conforms to SentinelOutput
        mock_response = {
            "hypotheses": [
                {
                    "rank": 1,
                    "root_cause": "ADCS_SENSOR_FAULT",
                    "affected_component": "GYRO_A",
                    "confidence": 0.90,
                    "causal_chain": ["SEU counter spike", "gyro NaN", "Safe mode"]
                },
                {
                    "rank": 2,
                    "root_cause": "ADCS_NOISE",
                    "affected_component": "GYRO_A",
                    "confidence": 0.08,
                    "causal_chain": ["noise spike", "Safe mode"]
                },
                {
                    "rank": 3,
                    "root_cause": "FALSE_ALARM",
                    "affected_component": "NONE",
                    "confidence": 0.02,
                    "causal_chain": ["temporary glitch", "Safe mode"]
                }
            ],
            "recovery_plan": [
                {
                    "step": 1,
                    "command": "CMD_GYRO_A_RESET",
                    "rationale": "Clear potential SEU bit flip",
                    "wait_seconds": 30,
                    "verify": "gyro output returns to normal",
                    "risk": "LOW"
                }
            ],
            "confidence": 0.90,
            "requires_human_review": False,
            "reasoning_summary": "SEU spike occurred right before Gyro rate output went NaN.",
            "status": "complete"
        }
        mock_call_llm.return_value = json.dumps(mock_response)

        # Get first preset scenario
        scenarios_resp = self.client.get("/scenarios")
        scenario = scenarios_resp.json()[0]

        # Call POST /analyze
        # SSE stream yields: "data: <json>\n\n"
        response = self.client.post("/analyze", json=scenario)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")

        events = []
        for line in response.iter_lines():
            if isinstance(line, bytes):
                line_str = line.decode("utf-8").strip()
            else:
                line_str = str(line).strip()
            if line_str.startswith("data: "):
                data_str = line_str[len("data: "):]
                event = json.loads(data_str)
                events.append(event)

        # Verify event stream composition
        self.assertGreater(len(events), 0)
        
        event_types = [e["event_type"] for e in events]
        self.assertIn("status", event_types)
        self.assertIn("thought", event_types)
        self.assertIn("observation", event_types)
        self.assertIn("result", event_types)

        # Verify the result event payload
        result_event = next(e for e in events if e["event_type"] == "result")
        result_data = json.loads(result_event["data"])
        self.assertIn("hypotheses", result_data)
        self.assertEqual(result_data["confidence"], 0.90)

if __name__ == "__main__":
    unittest.main()
