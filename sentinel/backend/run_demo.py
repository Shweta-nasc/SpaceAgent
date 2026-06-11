import json
import asyncio
from agent import SentinelAgent
from scenarios import get_preset_scenarios

async def main():
    agent = SentinelAgent()
    # Get the first preset scenario (ADCS Sensor Fault)
    scenario = get_preset_scenarios()[0]
    
    print("🚀 Starting local demo of SENTINEL backend...")
    print("Analyzing Scenario 1: ADCS Sensor Fault (Gyro SEU spike)")
    print("=" * 60)
    
    # Mock _call_llm to execute locally without requiring an API key
    def mock_call_llm(messages):
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
                    "verify": "gyro output returns normal",
                    "risk": "LOW"
                }
            ],
            "confidence": 0.90,
            "requires_human_review": False,
            "reasoning_summary": "SEU spike occurred right before Gyro rate output went NaN.",
            "status": "complete"
        }
        return json.dumps(mock_response)
    
    agent._call_llm = mock_call_llm
    
    # Iterate over the analyze_crash_dump_stream generator
    for event in agent.analyze_crash_dump_stream(scenario):
        print(f"[{event.event_type.upper()}]")
        if event.event_type == "result":
            # Pretty print final result JSON
            data_dict = json.loads(event.data)
            print(json.dumps(data_dict, indent=2))
        else:
            print(event.data)
        print("-" * 60)
        # Add a tiny delay
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())
