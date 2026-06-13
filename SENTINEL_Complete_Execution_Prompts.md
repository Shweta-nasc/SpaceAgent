# SENTINEL — Complete Execution Prompts (All Issues Found & Fixed)
## Full Audit Results + Structured Prompts with Tests

---

## MASTER AUDIT — 8 Issues Found

| # | Issue | Severity | Blocks |
|---|---|---|---|
| 1 | **SCHEMA MISMATCH**: `prompts.py` fault names ≠ `evaluator.py` fault names ≠ `fault_simulator.py` | 🔴 CRITICAL | Accuracy = 0% |
| 2 | **MISSING `affected_component` in OUTPUT_FORMAT**: `prompts.py` schema block doesn't show it | 🔴 CRITICAL | Pydantic fails constantly |
| 3 | **AGENT INCOMPLETE**: No SSE streaming, no `analyze_crash_dump_stream()` | 🔴 CRITICAL | Frontend receives nothing live |
| 4 | **TIMEOUT NOT APPLIED**: `timeout_seconds=90` defined but never enforced | 🟠 HIGH | Demo hangs forever |
| 5 | **NO GRACEFUL FAILURE**: All retries fail → exception, main.py crashes with 500 | 🟠 HIGH | Demo crashes on stage |
| 6 | **EVALUATOR/RUN_EVALUATION DISCONNECT**: May be scoring separately from agent | 🟠 HIGH | Eval numbers are wrong |
| 7 | **FAULT TYPE NAME TRIPLE MISMATCH**: simulator → one set, prompts → different set, evaluator → first set again | 🔴 CRITICAL | Every eval metric is garbage |
| 8 | **DATASET FINE-TUNE MISMATCH**: dataset_generator uses simulator fault names, fine-tune teaches different names | 🟠 HIGH | Fine-tuned model broken |

---

## THE ROOT CAUSE OF ALL ISSUES

Everything traces to one decision: fault type names were defined THREE times with different spellings.

```text
fault_simulator.py     →  EPS_POWER_FAULT, ADCS_SENSOR_FAULT, OBC_SOFTWARE_FAULT, TCS_THERMAL_FAULT, COMMS_FAULT, MULTI_SYSTEM_CASCADE
prompts.py signatures  →  EPS_SOLAR_UNDERVOLT, ADCS_GYRO_SEU, OBC_WATCHDOG_OVERFLOW, TCS_THERMAL_RUNAWAY, COMMS_TRANSPONDER_LOSS, MULTI_CASCADE
evaluator.py registry  →  EPS_POWER_FAULT, ADCS_SENSOR_FAULT, OBC_SOFTWARE_FAULT, TCS_THERMAL_FAULT, COMMS_FAULT, MULTI_SYSTEM_CASCADE
```

The LLM is taught in prompts.py to output `ADCS_GYRO_SEU`.
The evaluator scores for exact match against `ADCS_SENSOR_FAULT`.
Result: **fault_class_accuracy = 0% always**. This must be fixed first before anything else.

**Decision (pick ONE and apply everywhere):**  
Use the prompts.py names because they are more precise and what the LLM already outputs:

```text
ADCS_GYRO_SEU, EPS_SOLAR_UNDERVOLT, OBC_WATCHDOG_OVERFLOW,
TCS_THERMAL_RUNAWAY, COMMS_TRANSPONDER_LOSS, MULTI_CASCADE
```

---

## EXECUTION ORDER (DO THIS EXACTLY)

```text
STEP 0  →  Fix fault type names everywhere (30 min) — MUST BE FIRST
STEP 1  →  Fix prompts.py OUTPUT_FORMAT schema block (15 min)
STEP 2  →  Fix fault_simulator.py to use new names + add tests (45 min)
STEP 3  →  Fix evaluator.py GROUND_TRUTH_REGISTRY (30 min)
STEP 4  →  Add SSE streaming to agent.py + main.py (60 min)
STEP 5  →  Add hard timeout + graceful failure partial output (30 min)
STEP 6  →  Verify run_evaluation.py calls evaluator.py correctly (20 min)
STEP 7  →  Fix dataset_generator.py fault names (15 min)
STEP 8  →  Run full test suite — must get green
STEP 9  →  Run 5x demo reliability check on 3 scenarios
STEP 10 →  ESA real data integration test
```

---

---

# PROMPT 0 — SCHEMA ALIGNMENT FIX
## “Fix the fault type name mismatch everywhere before touching anything else”

```text
You are my coding assistant for SENTINEL, a spacecraft fault diagnosis hackathon project.

I have a CRITICAL bug: fault type names are inconsistent across three files.
This causes fault_class_accuracy = 0% because the LLM outputs one name
and the evaluator scores a different name.

## The Problem

fault_simulator.py generates crash dumps with these fault_type values:
  EPS_POWER_FAULT, ADCS_SENSOR_FAULT, OBC_SOFTWARE_FAULT,
  TCS_THERMAL_FAULT, COMMS_FAULT, MULTI_SYSTEM_CASCADE

prompts.py teaches the LLM to recognize and output:
  EPS_SOLAR_UNDERVOLT, ADCS_GYRO_SEU, OBC_WATCHDOG_OVERFLOW,
  TCS_THERMAL_RUNAWAY, COMMS_TRANSPONDER_LOSS, MULTI_CASCADE

evaluator.py GROUND_TRUTH_REGISTRY keys are:
  EPS_POWER_FAULT, ADCS_SENSOR_FAULT, OBC_SOFTWARE_FAULT,
  TCS_THERMAL_FAULT, COMMS_FAULT, MULTI_SYSTEM_CASCADE

The LLM outputs ADCS_GYRO_SEU but evaluator expects ADCS_SENSOR_FAULT → miss.

## The Fix — Canonical Names (USE THESE EVERYWHERE)

The canonical fault type names from now on are the SPECIFIC ones from prompts.py
because they describe WHAT happened, not just which subsystem:

  ADCS_GYRO_SEU         (was: ADCS_SENSOR_FAULT)
  EPS_SOLAR_UNDERVOLT   (was: EPS_POWER_FAULT)
  OBC_WATCHDOG_OVERFLOW (was: OBC_SOFTWARE_FAULT)
  TCS_THERMAL_RUNAWAY   (was: TCS_THERMAL_FAULT)
  COMMS_TRANSPONDER_LOSS (was: COMMS_FAULT)
  MULTI_CASCADE         (was: MULTI_SYSTEM_CASCADE)

## Task 1 — Update fault_simulator.py

In fault_simulator.py:
1. Change _VALID_FAULT_TYPES frozenset to use the new canonical names
2. Change every method that generates a crash dump to use the new fault_type values:
   - generate_crash_dump() method: the returned dict "fault_type" field
   - All 6 private fault generator methods: their fault_register strings and labels
   - _generate_eps_power_fault() → should now generate dumps with fault_type = "EPS_SOLAR_UNDERVOLT"
   - _generate_adcs_sensor_fault() → fault_type = "ADCS_GYRO_SEU"
   - _generate_obc_software_fault() → fault_type = "OBC_WATCHDOG_OVERFLOW"
   - _generate_tcs_thermal_fault() → fault_type = "TCS_THERMAL_RUNAWAY"
   - _generate_comms_fault() → fault_type = "COMMS_TRANSPONDER_LOSS"
   - _generate_multi_cascade() → fault_type = "MULTI_CASCADE"
3. Update get_ground_truth() method: change all 6 root_cause_classification values
   to use the new canonical names
4. Keep the method names unchanged (internal implementation detail)

## Task 2 — Update evaluator.py GROUND_TRUTH_REGISTRY

Change all 6 GROUND_TRUTH_REGISTRY keys AND their "root_cause" values
to use the canonical names:

  "ADCS_GYRO_SEU": { "root_cause": "ADCS_GYRO_SEU", ... }
  "EPS_SOLAR_UNDERVOLT": { "root_cause": "EPS_SOLAR_UNDERVOLT", ... }
  "OBC_WATCHDOG_OVERFLOW": { "root_cause": "OBC_WATCHDOG_OVERFLOW", ... }
  "TCS_THERMAL_RUNAWAY": { "root_cause": "TCS_THERMAL_RUNAWAY", ... }
  "COMMS_TRANSPONDER_LOSS": { "root_cause": "COMMS_TRANSPONDER_LOSS", ... }
  "MULTI_CASCADE": { "root_cause": "MULTI_CASCADE", ... }

Keep all other fields (confidence, risk_level, keywords, etc.) unchanged.
Also update DEMO_FAULT_TYPES list at the bottom.

## Task 3 — Update dataset_generator.py

In dataset_generator.py, anywhere it references the old fault type names
(ADCS_SENSOR_FAULT, EPS_POWER_FAULT, etc.) update them to the canonical names.
Also update any labels in generated JSONL training data samples.

## Tests to Write (write these AFTER making all changes)

File: test_schema_alignment.py

Tests to include:

1. test_simulator_fault_types_canonical()
   - Generate one crash dump for each of the 6 canonical fault types
   - Assert dump["fault_type"] matches the canonical name exactly
   - Assert fault_type is a key in GROUND_TRUTH_REGISTRY

2. test_ground_truth_registry_alignment()
   - For each key in GROUND_TRUTH_REGISTRY:
     assert key == GROUND_TRUTH_REGISTRY[key]["root_cause"]
   - Assert all 6 canonical names are present as keys

3. test_evaluator_scores_correct_name()
   - Create a mock response dict with root_cause = "ADCS_GYRO_SEU" rank 1
   - Call evaluate_response(mock_response, "ADCS_GYRO_SEU")
   - Assert fault_class_correct = True
   - Also test that evaluate_response with root_cause = "ADCS_SENSOR_FAULT" (old name)
     returns fault_class_correct = False (to confirm old names no longer accepted)

4. test_prompts_fault_signature_names_match_registry()
   - Import FAULT_SIGNATURES string from prompts.py
   - For each canonical name, assert it appears in FAULT_SIGNATURES
   - This confirms prompts.py teaches the LLM exactly the names evaluator expects

5. test_no_old_names_in_simulator()
   - Import SatelliteFaultSimulator
   - Assert "EPS_POWER_FAULT" not in sim._VALID_FAULT_TYPES
   - Assert "ADCS_SENSOR_FAULT" not in sim._VALID_FAULT_TYPES
   - (same for all 6 old names)

Run command: python -m pytest test_schema_alignment.py -v
Expected: 5/5 tests pass

Show me the updated _VALID_FAULT_TYPES in fault_simulator.py first.
Then show the updated GROUND_TRUTH_REGISTRY keys in evaluator.py.
Then write test_schema_alignment.py.
```

---

---

# PROMPT 1 — FIX OUTPUT_FORMAT IN PROMPTS.PY
## “The system prompt schema block is missing affected_component — LLM never includes it, Pydantic always fails”

```text
You are my coding assistant for SENTINEL.

## The Problem

In prompts.py, the OUTPUT_FORMAT section shows this JSON schema to the LLM:

"hypotheses": [
  {
    "rank": 1,
    "root_cause": "",
    "confidence": ,
    "causal_chain": [...]
  }
]

BUT models.py Hypothesis requires:
  - rank (int, 1-3) ✅
  - root_cause (str) ✅
  - affected_component (str, min_length=2) ❌ MISSING FROM SCHEMA SHOWN TO LLM
  - confidence (float) ✅
  - causal_chain (List[str], min 2 items) ✅

Because affected_component is NOT in the OUTPUT_FORMAT schema block,
the LLM does not include it. Pydantic validation fails EVERY TIME.
The retry fires, the repair prompt mentions affected_component, sometimes
the second attempt works — but this means EVERY call has at least 2 LLM
calls, doubling latency, and sometimes fails even then.

## The Fix

Update the OUTPUT_FORMAT constant in prompts.py.

The schema block for each hypothesis must show:
{
  "rank": 1,
  "root_cause": "<fault class e.g. ADCS_GYRO_SEU>",
  "affected_component": "<specific component e.g. GYRO_A>",
  "confidence": <0.0-1.0>,
  "causal_chain": [
    "<event 1>",
    "<event 2>",
    "<event 3>"
  ]
}

Also add an explanatory note:
"affected_component: the specific hardware component (e.g. GYRO_A, SOLAR_ARRAY_A, TRANSPONDER_B)"

## Full Corrected OUTPUT_FORMAT Block

Replace the entire OUTPUT_FORMAT constant. Here is what it must contain:

Header line: "OUTPUT FORMAT — STRICT JSON, NO EXCEPTIONS:"

Then a description of the root-level object:
{
  "hypotheses": [3 items, see below],
  "recovery_plan": [1 or more steps, see below],
  "confidence": <float matching rank-1 hypothesis confidence>,
  "requires_human_review": <true if confidence < 0.70 or any step is HIGH risk>,
  "reasoning_summary": "<2-4 sentences>"
}

Each hypothesis item:
{
  "rank": <1, 2, or 3>,
  "root_cause": "<fault class — must match known fault signatures>",
  "affected_component": "<specific hardware component, e.g. GYRO_A, SOLAR_ARRAY_A>",
  "confidence": <float 0.0-1.0>,
  "causal_chain": ["<event 1>", "<event 2>", "<event 3 or more>"]
}

Each recovery_plan step:
{
  "step": <1-indexed integer>,
  "command": "<CMD_UPPER_SNAKE_CASE>",
  "rationale": "<why this command now>",
  "wait_seconds": <integer seconds to wait before verifying>,
  "verify": "<condition to check after wait>",
  "risk": "<LOW | MEDIUM | HIGH>"
}

Rules at the bottom (keep existing ones, add):
"- Each hypothesis MUST include affected_component (the hardware component, not the subsystem)"
"- affected_component examples: GYRO_A, GYRO_B, SOLAR_ARRAY_A, TRANSPONDER_B, HEATER_ZONE_1, OBC_CPU"

## Tests to Write

File: test_output_format.py

1. test_output_format_contains_affected_component()
   - Import OUTPUT_FORMAT from prompts.py
   - Assert "affected_component" in OUTPUT_FORMAT
   - Assert "GYRO_A" in OUTPUT_FORMAT (example must appear)

2. test_build_messages_schema_integrity()
   - Call build_messages(crash_dump_json='{"test": true}')
   - Assert messages["role"] == "system"
   - Assert "affected_component" in messages["content"]
   - Assert "wait_seconds" in messages["content"]

3. test_repair_prompt_matches_schema()
   - Import _REPAIR_PROMPT from agent.py
   - Assert "affected_component" in _REPAIR_PROMPT
   - Assert "wait_seconds" in _REPAIR_PROMPT

4. test_pydantic_validates_complete_llm_output()
   - Build a minimal valid dict that matches the schema:
     hypotheses with rank 1/2/3, each with affected_component,
     recovery_plan with 2 steps, confidence=0.85, requires_human_review=False,
     reasoning_summary="Test."*3
   - Call SentinelOutput.model_validate(valid_dict)
   - Assert no exception raised

5. test_pydantic_rejects_missing_affected_component()
   - Build a dict with hypotheses that have NO affected_component field
   - Assert SentinelOutput.model_validate(bad_dict) raises ValidationError

Run command: python -m pytest test_output_format.py -v
Expected: 5/5 pass

Show me the full updated OUTPUT_FORMAT constant first.
```

---

---

# PROMPT 2 — FIX AGENT.PY COMPLETION + ADD SSE STREAMING
## “Agent is missing streaming. Add analyze_crash_dump_stream() and wire it to main.py”

```text
You are my coding assistant for SENTINEL.

## What's Missing in agent.py

The agent docstring lists "Step 11: SSE streaming via analyze_crash_dump_stream()"
as a FUTURE integration point that is NOT YET IMPLEMENTED.

main.py is only 2422 chars — it likely has a synchronous endpoint.
The frontend needs SSE (Server-Sent Events) streaming with these event types:
  {"type": "thought", "content": "...", "timestamp": 1234.56}
  {"type": "action",  "content": "...", "timestamp": 1234.56}
  {"type": "observation", "content": "...", "timestamp": 1234.56}
  {"type": "result", "content": "<full SentinelOutput JSON>", "timestamp": 1234.56}
  {"type": "error",  "content": "...", "timestamp": 1234.56}

## Task 1 — Add analyze_crash_dump_stream() to agent.py

Add this async generator method to the SentinelAgent class:

async def analyze_crash_dump_stream(
    self,
    crash_dump: dict | str,
    anomalous_parameters: list[str] | None = None,
    retrieved_procedures: list[str] | None = None,
    system_prompt_override: str | None = None,
) -> AsyncGenerator[dict, None]:

It must yield SSE event dicts at each pipeline stage:

Stage 1 — yield thought: "Parsing crash dump and extracting telemetry..."
Stage 2 — yield action: "Running z-score anomaly pre-filter on {N} parameters..."
Stage 3 — yield observation: "Anomalous parameters: {param_list}"
Stage 4 — yield action: "Retrieving ECSS procedures via RAG for query: {query}"
Stage 5 — yield observation: "Retrieved {N} procedure snippet(s)"
Stage 6 — yield action: "Calling {model_name} for fault diagnosis..."
Stage 7 — yield thought: "Parsing and validating LLM response..."
Stage 8 — yield action: "Running safety validator on {N} recovery steps..."
Stage 9 — yield observation: "Safety check: {N_blocked} blocked, {N_ok} approved. {safety_summary}"
Stage 10 — yield result: the full SentinelOutput serialized as JSON string

On any exception: yield error event and return.

Each yielded dict must have exactly: {"type": str, "content": str, "timestamp": float}
Use time.time() for timestamp.

IMPORTANT: The actual LLM call (Stage 6) must run in a thread executor
because google-genai is synchronous. Use:
  import asyncio
  loop = asyncio.get_event_loop()
  raw_response = await loop.run_in_executor(None, self._call_llm, messages)

## Task 2 — Add Hard Timeout

In analyze_crash_dump() (the synchronous version), add timeout enforcement:

import threading

def _run_with_timeout(fn, timeout_seconds, *args, **kwargs):
    result = [None]
    error = [None]
    def target():
        try:
            result = fn(*args, **kwargs)
        except Exception as e:
            error = e
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=timeout_seconds)
    if t.is_alive():
        raise TimeoutError(f"Agent exceeded {timeout_seconds}s timeout")
    if error:
        raise error
    return result

Wrap the self._call_llm(messages) call inside _run_with_timeout.

In analyze_crash_dump_stream(), use asyncio.wait_for on the run_in_executor call:
  raw_response = await asyncio.wait_for(
      loop.run_in_executor(None, self._call_llm, messages),
      timeout=self.config.timeout_seconds
  )

## Task 3 — Add Graceful Partial Output on Failure

Add a class method or helper that returns a safe partial SentinelOutput
when the agent fails after all retries:

@staticmethod
def _make_timeout_output(reason: str) -> SentinelOutput:
    return SentinelOutput(
        hypotheses=[
            Hypothesis(rank=1, root_cause="UNKNOWN", affected_component="UNKNOWN",
                      confidence=0.0, causal_chain=["Diagnosis failed", reason]),
            Hypothesis(rank=2, root_cause="UNKNOWN", affected_component="UNKNOWN",
                      confidence=0.0, causal_chain=["Diagnosis failed", reason]),
            Hypothesis(rank=3, root_cause="UNKNOWN", affected_component="UNKNOWN",
                      confidence=0.0, causal_chain=["Diagnosis failed", reason]),
        ],
        recovery_plan=[RecoveryStep(
            step=1,
            command="CMD_REQUEST_HUMAN_REVIEW",
            rationale=f"Automated diagnosis failed: {reason}",
            wait_seconds=0,
            verify="Human operator reviews crash dump manually",
            risk=RiskLevel.HIGH
        )],
        confidence=0.0,
        requires_human_review=True,
        reasoning_summary=f"Diagnosis failed: {reason}. Human review required.",
        status=AnalysisStatus.ERROR
    )

In analyze_crash_dump(), when last_error is raised and all retries exhausted:
Instead of re-raising, log it and return self._make_timeout_output(str(last_error)).
Only still raise on LLMCallError (API auth/network failure — these are real errors
that should propagate, not be silently swallowed).

## Task 4 — Update main.py

main.py needs a proper SSE streaming endpoint. Replace the existing
/api/analyze endpoint (or add /api/analyze/stream) with:

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json, asyncio
from agent import SentinelAgent, AgentConfig

app = FastAPI(title="SENTINEL API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

@app.post("/api/analyze/stream")
async def analyze_stream(request: dict):
    agent = SentinelAgent()

    async def event_generator():
        async for event in agent.analyze_crash_dump_stream(
            crash_dump=request,
            anomalous_parameters=request.get("_anomalous_params"),
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})

@app.post("/api/analyze")
async def analyze_sync(request: dict):
    """Synchronous fallback for testing and demo cache."""
    agent = SentinelAgent()
    result = agent.analyze_with_rag(crash_dump=request)
    return result.model_dump()

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "SENTINEL"}

## Tests to Write

File: test_agent_streaming.py

1. test_stream_yields_all_event_types()
   - Use a mock LLM that returns a valid JSON string synchronously
   - Collect all events from analyze_crash_dump_stream(mock_crash_dump)
   - Assert at least one event of each type: thought, action, observation, result
   - Assert final event type == "result"

2. test_stream_result_event_is_valid_sentinel_output()
   - Run streaming with mock LLM
   - Find the "result" event
   - Parse event["content"] as JSON
   - Call SentinelOutput.model_validate(parsed) — should not raise

3. test_timeout_returns_partial_output()
   - Create AgentConfig with timeout_seconds=0.001 (immediate timeout)
   - Call analyze_crash_dump(valid_crash_dump)
   - Assert result is SentinelOutput (not exception)
   - Assert result.status == AnalysisStatus.ERROR
   - Assert result.requires_human_review == True
   - Assert result.confidence == 0.0

4. test_all_retries_exhausted_returns_partial_output()
   - Mock _call_llm to always return invalid JSON "not json at all"
   - Call analyze_crash_dump(valid_crash_dump)
   - Assert returns SentinelOutput (not exception)
   - Assert status == AnalysisStatus.ERROR

5. test_stream_error_event_on_failure()
   - Mock _call_llm to raise LLMCallError
   - Collect events from analyze_crash_dump_stream
   - Assert "error" event is yielded
   - Assert after "error" event, no more events

6. test_main_health_endpoint()
   - Use FastAPI TestClient
   - GET /api/health
   - Assert status_code == 200
   - Assert response["status"] == "ok"

Run command: python -m pytest test_agent_streaming.py -v
Expected: 6/6 pass

Show me the full analyze_crash_dump_stream() method first.
Then show the updated main.py.
```

---

---

# PROMPT 3 — FIX EVALUATOR + RUN_EVALUATION PIPELINE
## “Verify evaluator.py and run_evaluation.py are wired correctly and measure real metrics”

```text
You are my coding assistant for SENTINEL.

## Context

After Prompt 0 fixes fault type names, we need to verify the full
evaluation pipeline actually works end-to-end.

## Task 1 — Audit run_evaluation.py

Read run_evaluation.py and answer:
1. Does it import and call SentinelEvaluator from evaluator.py?
   OR does it have its own evaluation logic that duplicates evaluator.py?
2. Does it call agent.analyze_with_rag() for each test scenario?
   OR does it load pre-generated responses from a file?
3. Does it generate evaluation_results.json with the structure we need?
4. What is the test set — does it use a test.jsonl file? Does that file exist?

Show me the answer to these 4 questions by reading the actual code.

## Task 2 — Fix the Pipeline if Disconnected

If run_evaluation.py does NOT call evaluator.py, wire it:

from evaluator import SentinelEvaluator, GROUND_TRUTH_REGISTRY
evaluator = SentinelEvaluator("full_system")
# for each test scenario:
score = evaluator.add(json.dumps(result.model_dump()), true_fault_type, latency_ms)
report = evaluator.report()

If run_evaluation.py DOES call evaluator.py but evaluator.py has old fault names,
that's already fixed by Prompt 0. Verify it works after that fix.

## Task 3 — Add 4-Config Ablation Support

Add a --config flag to run_evaluation.py CLI:
  --config full        (default: agent + RAG + safety)
  --config no-rag      (disable RAG, use FALLBACK_KB only)
  --config no-safety   (skip safety.py validation)
  --config base-model  (no system prompt, raw LLM call only)

For no-rag: pass use_pdf_rag=False and fault_cues=[] to analyze_with_rag()
For no-safety: add skip_safety=True param to analyze_crash_dump(), bypass the
  safety.validate_recovery_plan() call when skip_safety=True
For base-model: call the LLM directly with user message = crash dump JSON only,
  no system prompt (system_prompt_override="")

## Task 4 — Add Missing Metric: safety_alignment_rate

Add should_be_safe to GROUND_TRUTH_REGISTRY for all 6 fault types:
  ADCS_GYRO_SEU: should_be_safe=True
  EPS_SOLAR_UNDERVOLT: should_be_safe=True
  OBC_WATCHDOG_OVERFLOW: should_be_safe=False
  TCS_THERMAL_RUNAWAY: should_be_safe=False
  COMMS_TRANSPONDER_LOSS: should_be_safe=True
  MULTI_CASCADE: should_be_safe=False

Add metric 9: safety_alignment_rate
  = % of scenarios where ValidationResult.is_safe matches should_be_safe
  = only computable when safety validation runs (full and no-rag configs)

## Tests to Write

File: test_evaluation_pipeline.py

1. test_run_evaluation_imports_evaluator()
   - Import SentinelEvaluator from evaluator.py
   - Assert it can be instantiated: SentinelEvaluator("test")
   - Assert evaluator.add() and evaluator.report() exist

2. test_evaluate_response_with_correct_canonical_name()
   - Build a valid mock response JSON with root_cause = "ADCS_GYRO_SEU"
   - Call evaluate_response(mock_json, "ADCS_GYRO_SEU")
   - Assert result["fault_class_correct"] == True

3. test_evaluate_response_with_wrong_name()
   - Same but root_cause = "ADCS_SENSOR_FAULT" (old name)
   - Assert result["fault_class_correct"] == False

4. test_ground_truth_has_should_be_safe()
   - For each key in GROUND_TRUTH_REGISTRY:
     assert "should_be_safe" in GROUND_TRUTH_REGISTRY[key]
   - Assert GROUND_TRUTH_REGISTRY["MULTI_CASCADE"]["should_be_safe"] == False
   - Assert GROUND_TRUTH_REGISTRY["ADCS_GYRO_SEU"]["should_be_safe"] == True

5. test_ablation_no_rag_config()
   - Create AgentConfig
   - Call agent.analyze_with_rag(crash_dump, use_pdf_rag=False) with a mock dump
   - Assert result is SentinelOutput

Run command: python -m pytest test_evaluation_pipeline.py -v
Expected: 5/5 pass

Show me what run_evaluation.py currently does first.
Then show the fixes.
```

---

---

# PROMPT 4 — ESA REAL DATA INTEGRATION + EARLY WARNING
## “Wire esa_adb_crash_dump.py to the agent and build early_warning.py”

```text
You are my coding assistant for SENTINEL.

## Context

esa_adb_crash_dump.py is a complete tool that converts ESA-ADB telemetry
into SENTINEL crash dump format. The file esa_mission1_id_109_sentinel_only.json
already exists — it's the compact agent-ready version.

The key limitation: ESA-ADB has NO engineering root cause labels.
We cannot score root_cause_accuracy on ESA data.
What we CAN test: does the agent produce valid output, set requires_human_review
correctly, and not hallucinate?

## Task 1 — ESA Real Data Integration Test

Write test_esa_integration.py:

Load esa_mission1_id_109_sentinel_only.json
Pass it to agent.analyze_with_rag() (full system config)
Check these 4 things (no accuracy claim):

1. valid_output: result is SentinelOutput (no exception)
2. human_review_set: result.requires_human_review == True
3. low_confidence: result.confidence < 0.80
4. no_hallucinated_param_names:
   reasoning_summary and hypothesis root_cause must not contain parameter names
   not in the crash dump

Save the result as data/esa_real_data_test_result.json with fields:
  valid_output, human_review_set, low_confidence, no_hallucinated_params,
  actual_confidence, actual_root_cause, actual_reasoning_summary

## Task 2 — Build early_warning.py

Create sentinel/backend/early_warning.py with this class:

@dataclass
class EarlyWarningAlert:
    warning_issued_at_offset: str
    anomalous_params: list[str]
    max_z_score: float
    suspected_fault_type: str
    confidence: float
    message: str

class EarlyWarningMonitor:
    def __init__(self, window_minutes=5, check_interval_seconds=60, z_threshold=2.5)

    def simulate_pre_fault(self, crash_dump: dict) -> list[EarlyWarningAlert]:
        pass

    def _heuristic_fault_type(self, anomalous_params: list[str]) -> tuple[str, float]:
        if "Gyro_rate_degs" in anomalous_params or "SEU_counter" in anomalous_params:
            return "ADCS_GYRO_SEU", 0.7
        elif "V_bat" in anomalous_params or "I_sa" in anomalous_params or "SoC_pct" in anomalous_params:
            return "EPS_SOLAR_UNDERVOLT", 0.7
        elif "CPU_load_pct" in anomalous_params or "Watchdog_counter" in anomalous_params:
            return "OBC_WATCHDOG_OVERFLOW", 0.7
        elif "Component_temp_C" in anomalous_params or "Heater_power_W" in anomalous_params:
            return "TCS_THERMAL_RUNAWAY", 0.7
        elif "Transponder_lock" in anomalous_params or "SNR_dB" in anomalous_params:
            return "COMMS_TRANSPONDER_LOSS", 0.7
        else:
            return "MULTI_CASCADE", 0.4

Demo scenario:
Generate an EPS_SOLAR_UNDERVOLT crash dump from simulator.
Run simulate_pre_fault on it.
Assert an alert is yielded at > T-60s before event.
Assert the suspected_fault_type is "EPS_SOLAR_UNDERVOLT".
Save output to data/early_warning_demo.json.

## Tests to Write

File: test_early_warning.py

1. test_early_warning_detects_eps_fault()
   - Generate EPS_SOLAR_UNDERVOLT crash dump
   - Run simulate_pre_fault on it
   - Assert len(alerts) >= 1
   - Assert at least one alert has suspected_fault_type == "EPS_SOLAR_UNDERVOLT"

2. test_early_warning_alert_timing()
   - Same as above
   - Assert alert warning_issued_at_offset starts with "T-"
   - Assert the offset seconds > 60

3. test_esa_data_valid_output()
   - Load esa_mission1_id_109_sentinel_only.json
   - Mock the LLM call to return a valid response
   - Assert mock result is SentinelOutput

4. test_no_hallucinated_params_in_esa_result()
   - Given a mock SentinelOutput for the ESA data
   - Check reasoning_summary does not contain "GYRO_A" or "V_bat"

Run command: python -m pytest test_early_warning.py -v
Expected: 4/4 pass
```

---

---

# PROMPT 5 — FULL SYSTEM INTEGRATION TEST + DEMO RELIABILITY
## “5x reliability check on all 3 demo scenarios before submitting”

```text
You are my coding assistant for SENTINEL.

This is the FINAL prompt. Run after ALL previous prompts are complete
and all test suites pass. This prompt verifies the complete system.

## Prerequisites (must all be green before running this prompt)

- test_schema_alignment.py: 5/5 ✅
- test_output_format.py: 5/5 ✅
- test_agent_streaming.py: 6/6 ✅
- test_evaluation_pipeline.py: 5/5 ✅
- test_early_warning.py: 4/4 ✅

## Task 1 — 5x Demo Reliability Check

Run each of the 3 demo scenarios through analyze_with_rag() exactly 5 times.
Log results in this table:

| Scenario | Fault Type | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Pass Rate |
|---|---|---|---|---|---|---|---|
| gyro_seu | ADCS_GYRO_SEU | | | | | | |
| solar_fault | EPS_SOLAR_UNDERVOLT | | | | | | |
| obc_watchdog | OBC_WATCHDOG_OVERFLOW | | | | | | |

Pass per run (ALL must be true):
✅ Valid SentinelOutput (no exception)
✅ Correct root_cause_class in rank-1 hypothesis
✅ Completed within 90 seconds
✅ recovery_plan has >= 3 steps
✅ reasoning_summary is non-empty
✅ requires_human_review value matches expected (True for obc_watchdog, can be either for others)

Target: 5/5 for all 3 scenarios.
If < 4/5: investigate and fix before calling done.

## Task 2 — Generate Cached Demo Responses

After 5x runs confirm reliability, save one good response for each scenario:
data/demo_cache/gyro_seu_cached.json
data/demo_cache/solar_fault_cached.json
data/demo_cache/obc_watchdog_cached.json

These are the BACKUP if live inference fails during the demo.
The frontend should have a "demo mode" button that loads these instead of
calling the API.

## Task 3 — Run Full Evaluation (4 configs × 20 scenarios)

Run run_evaluation.py with each config:
  python run_evaluation.py --config full --output results/eval_full.json
  python run_evaluation.py --config no-rag --output results/eval_no_rag.json
  python run_evaluation.py --config no-safety --output results/eval_no_safety.json
  python run_evaluation.py --config base-model --output results/eval_base_model.json

Collect results into evaluation_results.json:
{
  "run_timestamp": "...",
  "test_set_size": 20,
  "configs": {
    "full_system": {"fault_class_accuracy": X, "recovery_plan_adequacy": X, ...},
    "no_rag": {...},
    "no_safety": {...},
    "base_model": {...}
  },
  "ablation_delta": {
    "rag_contribution": "full - no_rag accuracy delta",
    "safety_contribution": "full safety_catch_rate vs no_safety",
    "system_prompt_contribution": "full vs base_model accuracy"
  },
  "pitch_summary": "Full system: XX% accuracy, XX% hallucination rate, XXs avg. ..."
}

## Tests to Write

File: test_integration.py

1. test_demo_scenario_gyro_seu_passes()
   Generate ADCS_GYRO_SEU crash dump, run analyze_with_rag(), assert pass criteria

2. test_demo_scenario_solar_fault_passes()
   Same for EPS_SOLAR_UNDERVOLT

3. test_demo_scenario_obc_watchdog_passes()
   Same for OBC_WATCHDOG_OVERFLOW
   Extra assert: result.requires_human_review == True

4. test_demo_cache_files_exist()
   Assert all 3 cached response files exist and are valid SentinelOutput JSON

5. test_stream_endpoint_returns_sse_events()
   Use FastAPI TestClient with streaming response
   POST /api/analyze/stream with a crash dump
   Assert response content-type is text/event-stream
   Assert at least one "data: " line is returned

Run command: python -m pytest test_integration.py -v
Expected: 5/5 pass

## Final Checklist Before Submission

- [ ] test_schema_alignment.py: 5/5
- [ ] test_output_format.py: 5/5
- [ ] test_agent_streaming.py: 6/6
- [ ] test_evaluation_pipeline.py: 5/5
- [ ] test_early_warning.py: 4/4
- [ ] test_integration.py: 5/5
- [ ] Demo scenarios: 15/15 (5 runs × 3 scenarios)
- [ ] evaluation_results.json exists with real numbers
- [ ] Demo cache files exist (3 files)
- [ ] GitHub repo has clean README, setup instructions, architecture diagram
- [ ] main.py /api/analyze/stream endpoint verified working
- [ ] /api/health returns 200
```

---

---

## SUMMARY TABLE

| Prompt | File Changed | Issue Fixed | Tests |
|---|---|---|---|
| 0 | fault_simulator.py, evaluator.py, dataset_generator.py | Fault type name triple mismatch | test_schema_alignment.py (5 tests) |
| 1 | prompts.py OUTPUT_FORMAT | Missing affected_component in schema shown to LLM | test_output_format.py (5 tests) |
| 2 | agent.py, main.py | Missing SSE streaming, no timeout enforcement, no graceful failure | test_agent_streaming.py (6 tests) |
| 3 | evaluator.py, run_evaluation.py | Evaluation pipeline disconnect, missing should_be_safe metric | test_evaluation_pipeline.py (5 tests) |
| 4 | early_warning.py (new), test_esa_integration.py | ESA data integration, early warning predictor | test_early_warning.py (4 tests) |
| 5 | demo_cache/ (new files), evaluation_results.json | Demo reliability, 4-config ablation, submission readiness | test_integration.py (5 tests) |

**Total new tests: 30 tests across 6 files**