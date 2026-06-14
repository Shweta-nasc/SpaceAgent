# SENTINEL Complete Execution Prompts

Project-leader version after Prompt 0 restructure.

This file is the control document for the remaining implementation prompts. It is aligned to the current repository structure under:

```text
sentinel/backend/app/
sentinel/backend/simulation/
sentinel/backend/tests/
sentinel/frontend/src/
```

Do not use old flat paths such as `agent.py`, `main.py`, `prompts.py`, `evaluator.py`, or `fault_simulator.py` at repository root. Those paths are stale.

## Current Source Of Truth

Key backend files:

```text
sentinel/backend/app/main.py
sentinel/backend/app/api/models.py
sentinel/backend/app/api/scenarios.py
sentinel/backend/app/agent/agent.py
sentinel/backend/app/agent/prompts.py
sentinel/backend/app/agent/rag.py
sentinel/backend/app/agent/safety.py
sentinel/backend/app/analytics/anomaly_detector.py
sentinel/backend/app/analytics/evaluator.py
sentinel/backend/app/analytics/run_evaluation.py
sentinel/backend/simulation/fault_simulator.py
sentinel/backend/simulation/dataset_generator.py
sentinel/backend/data_tools/esa_adb_crash_dump.py
```

Key frontend files:

```text
sentinel/frontend/src/App.jsx
sentinel/frontend/src/App.css
sentinel/frontend/public/index.html
sentinel/frontend/public/landing.html
```

Key data files:

```text
sentinel/backend/data/sentinel_training.jsonl
sentinel/backend/data/train.jsonl
sentinel/backend/data/valid.jsonl
sentinel/backend/data/esa_crash_dumps/mission1_summary.json
sentinel/backend/data/esa_crash_dumps/esa_mission1_id_109_crash_dump.json
sentinel/backend/data/esa_crash_dumps/esa_mission1_id_109_sentinel_only.json
```

## Non-Negotiable Contracts

Canonical fault classes:

```text
ADCS_GYRO_SEU
EPS_SOLAR_UNDERVOLT
OBC_WATCHDOG_OVERFLOW
TCS_THERMAL_RUNAWAY
COMMS_TRANSPONDER_LOSS
MULTI_CASCADE
```

LLM output schema:

```json
{
  "hypotheses": [
    {
      "rank": 1,
      "root_cause": "ADCS_GYRO_SEU",
      "affected_component": "GYRO_A",
      "confidence": 0.91,
      "causal_chain": ["event 1", "event 2"]
    }
  ],
  "recovery_plan": [
    {
      "step": 1,
      "command": "CMD_VERIFY_SEU_COUNTER",
      "rationale": "why this command is first",
      "wait_seconds": 5,
      "verify": "what telemetry proves success",
      "risk": "LOW"
    }
  ],
  "confidence": 0.91,
  "requires_human_review": true,
  "reasoning_summary": "short explanation"
}
```

SSE event schema for the React dashboard:

```json
{
  "event_type": "thought",
  "data": "plain text or JSON string",
  "step_number": 1
}
```

Do not replace this with `{"type": "...", "content": "...", "timestamp": ...}`. That is the old draft format and does not match `SSEEvent` in `sentinel/backend/app/api/models.py`.

Primary API routes:

```text
GET  /health
GET  /api/health
GET  /scenarios
GET  /api/scenarios
POST /analyze
POST /api/analyze
GET  /api/analyze    # compatibility EventSource route for public/index.html
```

If you add `/api/analyze/stream`, keep it as a backwards-compatible alias. Do not remove the current routes.

ESA-ADB truth boundary:

```text
ESA-ADB gives real anonymized telemetry, telecommand timing, anomaly intervals, affected channels, and event taxonomy.
ESA-ADB does not give engineering root cause, confirmed safe-mode state, spacecraft command names, or recovery labels.
Synthetic incidents provide root-cause and recovery supervision.
```

## Recommended Frontend Demo Flow

Use both a live-looking flow and reliable presets.

1. Live Safe-Mode Stream:
   - Start in `NOMINAL`.
   - Stream telemetry values.
   - Highlight an anomaly.
   - Transition `NOMINAL -> ALERT -> SAFE_MODE`.
   - Freeze the pre-fault telemetry window.
   - Generate a crash-dump JSON.
   - Start the agent and stream reasoning.
   - Show hypotheses, causal chain, recovery plan, and safety/human-review gate.

2. Incident Library:
   - `Synthetic Safe Mode: ADCS Gyro SEU`
   - `Synthetic Safe Mode: EPS Solar Undervolt`
   - `Synthetic Safe Mode: OBC Watchdog Overflow`
   - `Synthetic Safe Mode: TCS Thermal Runaway`
   - `Real ESA Telemetry: id_109 Multivariate Anomaly`
   - `Real ESA Telemetry: Communication Gap`

3. Upload/Paste Crash Dump JSON:
   - Keep this for judge questions and quick modified-input demos.

The source label must be visible in the UI. Do not imply ESA examples have confirmed recovery labels.

## Execution Order

Run this order:

```text
PROMPT 0.5 -> contract audit after restructure
PROMPT 1   -> schema, prompt, dataset, and test alignment
PROMPT 2   -> API streaming and frontend integration
PROMPT 3   -> evaluation pipeline and ablations
PROMPT 4   -> ESA real telemetry and early warning
PROMPT 5   -> final demo reliability and submission hardening
```

Prompt 0 was the restructure. Do not run another broad restructure unless a current test proves it is necessary.

---

# PROMPT 0.5 - POST-RESTRUCTURE CONTRACT AUDIT

```text
You are my coding assistant and project lead for SENTINEL.

I already ran Prompt 0 and the repository has been restructured. Before changing feature code, audit the current structure and contracts.

Read these files first:

- SENTINEL_4Day_Master_Planner.md
- SENTINEL_Hackathon_Strategy_v2.md
- sentinel/docs/person1_esa_crash_dump_workflow.md
- sentinel/backend/app/main.py
- sentinel/backend/app/api/models.py
- sentinel/backend/app/api/scenarios.py
- sentinel/backend/app/agent/agent.py
- sentinel/backend/app/agent/prompts.py
- sentinel/backend/simulation/fault_simulator.py
- sentinel/backend/simulation/dataset_generator.py
- sentinel/backend/app/analytics/evaluator.py
- sentinel/backend/app/analytics/run_evaluation.py
- sentinel/frontend/src/App.jsx

Tasks:

1. Print the active source tree summary. Confirm that active backend code is under `sentinel/backend/app` and `sentinel/backend/simulation`.
2. Confirm `sentinel/backend/data_tools/esa_adb_crash_dump.py` exists. If it only exists under `__pycache__`, restore the source file to `sentinel/backend/data_tools/esa_adb_crash_dump.py`.
3. Search for stale labels outside intentional negative tests:
   - EPS_POWER_FAULT
   - ADCS_SENSOR_FAULT
   - OBC_SOFTWARE_FAULT
   - TCS_THERMAL_FAULT
   - COMMS_FAULT
   - MULTI_SYSTEM_CASCADE
4. Search generated JSONL for stale `"component"` output keys. Training labels must use `"affected_component"`.
5. Confirm React expects SSE fields `event_type`, `data`, and `step_number`.
6. Confirm backend has `/health`, `/api/health`, `/scenarios`, `/api/scenarios`, `/analyze`, and `/api/analyze` routes.
7. Run targeted tests:
   - `venv/bin/python -m pytest sentinel/backend/tests/test_schema_alignment.py -q`
   - `venv/bin/python -m pytest sentinel/backend/tests/test_pipeline.py -q`
   - `venv/bin/python -m pytest sentinel/backend/tests/test_generate_crash_dump.py -q`
   - `venv/bin/python sentinel/backend/tests/test_models.py`

Fix only confirmed contract mismatches. Do not rewrite the architecture.

At the end, report:

- What files exist now.
- Which stale references remain and whether they are intentional negative tests.
- Which tests passed.
- Whether Prompts 1-5 can run safely.
```

---

# PROMPT 1 - SCHEMA, PROMPT, DATASET, AND TEST ALIGNMENT

```text
You are my coding assistant for SENTINEL.

Goal: Validate that the schema, prompt, simulator, generated labels, and tests all agree. The codebase should already be perfectly aligned. If you find any misalignment or issues that are not as intended, make the necessary improvements.

Use these actual paths:

- sentinel/backend/app/api/models.py
- sentinel/backend/app/agent/prompts.py
- sentinel/backend/simulation/fault_simulator.py
- sentinel/backend/simulation/dataset_generator.py
- sentinel/backend/app/analytics/evaluator.py
- sentinel/backend/tests/
- sentinel/backend/data/

Required canonical fault classes:

- ADCS_GYRO_SEU
- EPS_SOLAR_UNDERVOLT
- OBC_WATCHDOG_OVERFLOW
- TCS_THERMAL_RUNAWAY
- COMMS_TRANSPONDER_LOSS
- MULTI_CASCADE

Tasks:

1. Validate `SentinelOutput`, `Hypothesis`, and `RecoveryStep` in `app/api/models.py`.
   - `Hypothesis` must require `affected_component`, not `component`.
   - Exactly 3 hypotheses must validate.
   - Recovery steps must include `step`, `command`, `rationale`, `wait_seconds`, `verify`, and `risk`.
   - If not as intended, make improvements.

2. Validate `OUTPUT_FORMAT` in `app/agent/prompts.py`.
   - It must show `affected_component`.
   - It must not show `"component"` as an output key.
   - It must use canonical fault names.
   - It must tell the model not to fabricate telemetry parameter names.
   - If not as intended, make improvements.

3. Validate `simulation/fault_simulator.py`.
   - `_VALID_FAULT_TYPES` must use only canonical names.
   - `generate_crash_dump()` must echo the canonical `fault_type`.
   - `get_ground_truth()` must return canonical `root_cause_classification`.
   - If not as intended, make improvements.

4. Validate `simulation/dataset_generator.py`.
   - Generated assistant JSON must use `affected_component`.
   - Generated root causes must use canonical names.
   - Generated recovery commands must be valid `CMD_UPPER_SNAKE_CASE`.
   - Prefer commands already in `app/agent/safety.py` whitelist.
   - If not as intended, make improvements.

5. Only regenerate dataset files if you had to make changes to the generator:
   - `sentinel/backend/data/sentinel_training.jsonl` with 600 examples.
   - `sentinel/backend/data/train.jsonl` with first 540 lines.
   - `sentinel/backend/data/valid.jsonl` with last 60 lines.

6. Run the test suite. Update tests ONLY if they contradict canonical names.
   - Keep intentional negative tests for old names.
   - Do not delete useful tests just to make the suite pass.

Validation commands:

```bash
venv/bin/python -m pytest sentinel/backend/tests/test_schema_alignment.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_pipeline.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_generate_crash_dump.py -q
venv/bin/python sentinel/backend/tests/test_models.py
rg -n 'EPS_POWER_FAULT|ADCS_SENSOR_FAULT|OBC_SOFTWARE_FAULT|TCS_THERMAL_FAULT|COMMS_FAULT|MULTI_SYSTEM_CASCADE|"component"' sentinel/backend/data --glob '*.jsonl'
```

Expected:

- The test commands pass.
- The final `rg` over JSONL returns no stale old labels and no `"component"` output keys.
```

---

# PROMPT 2 - API STREAMING AND FRONTEND INTEGRATION

```text
You are my coding assistant for SENTINEL.

Goal: Validate that the backend/frontend streaming path is reliable and that the current schema is used correctly. The SSE models, streaming endpoints, and React parser should already be implemented. If you find any issues that are not as intended, make the necessary improvements.

Use these actual paths:

- sentinel/backend/app/main.py
- sentinel/backend/app/api/models.py
- sentinel/backend/app/api/scenarios.py
- sentinel/backend/app/agent/agent.py
- sentinel/frontend/src/App.jsx
- sentinel/frontend/src/App.css
- sentinel/frontend/public/index.html

Important current contract:

- React dashboard posts crash dumps to `POST /analyze` or `POST /api/analyze`.
- Backend streams SSE chunks as `data: <SSEEvent JSON>`.
- `SSEEvent` JSON fields are `event_type`, `data`, and `step_number`.
- `event_type` values are `status`, `thought`, `action`, `observation`, `result`, and `error`.
- `result.data` is a JSON string matching `SentinelOutput`.
- `GET /api/analyze` exists separately for the static `public/index.html` EventSource client and maps events to `telemetry`, `trace`, and `done`.

Tasks:

1. Validate `app/main.py` routes.
   - Ensure `/health` and `/api/health` exist.
   - Ensure `/scenarios` and `/api/scenarios` exist.
   - Ensure `/analyze` and `/api/analyze` exist.
   - Ensure `GET /api/analyze` exists if `public/index.html` uses it.
   - If not as intended, make improvements.

2. Validate `SentinelAgent.analyze_crash_dump_stream()` in `app/agent/agent.py`.
   - It must yield `SSEEvent` objects, not raw dicts.
   - It must emit useful staged events: ingest, anomaly detection, RAG retrieval, LLM reasoning, safety validation/result.
   - On failure, it must emit an `error` event and not crash the server.
   - If not as intended, make improvements.

3. Validate React parsing in `frontend/src/App.jsx`.
   - It must parse `data: ...` SSE blocks from the POST stream.
   - It must route by `event.event_type`.
   - It must parse `event.data` as JSON only for `result`.
   - It must not expect `type/content/timestamp`.
   - If not as intended, make improvements.

4. Improve frontend scenario display if needed.
   - Show source type: `Synthetic Safe Mode` vs `Real ESA Telemetry`.
   - Keep custom JSON paste/upload.
   - Avoid overclaiming ESA examples as confirmed root-cause cases.

5. Validate tests. Add or update tests with mocked LLM calls if needed.
   - No real Gemini/OpenAI call in tests.
   - Test `/api/health`.
   - Test `/api/scenarios`.
   - Test POST `/api/analyze` returns `text/event-stream`.
   - Test the first few streamed events have fields `event_type` and `data`.
   - Test a final `result` event validates as `SentinelOutput`.

Validation commands:

```bash
venv/bin/python -m pytest sentinel/backend/tests/test_schema_alignment.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_pipeline.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_agent.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_rag.py -q
```

If script-style tests call `sys.exit()` at import time, run them directly instead of through pytest and report that clearly.
```

---

# PROMPT 3 - EVALUATION PIPELINE AND REAL METRICS

```text
You are my coding assistant for SENTINEL.

Goal: Validate that the evaluation framework produces defensible real numbers, without inventing metrics. `evaluator.py` and `run_evaluation.py` should already be fully implemented with 8 specific metrics. If you find any issues that are not as intended, make the necessary improvements.

Use these actual paths:

- sentinel/backend/app/analytics/evaluator.py
- sentinel/backend/app/analytics/run_evaluation.py
- sentinel/backend/app/agent/agent.py
- sentinel/backend/simulation/fault_simulator.py
- sentinel/backend/data/

Current situation to validate:

1. `evaluator.py` scores response JSON against canonical ground truth registry.
2. `run_evaluation.py` is a file-response evaluator rather than a live-agent runner.
3. Generated training JSONL is not the same thing as held-out live evaluation results.

Tasks:

1. Read and validate `run_evaluation.py`:
   - Does it import the real `SentinelEvaluator`?
   - Does it load response files, run the live agent, or both?
   - What JSONL shape does it expect?
   - What output files does it write?
   - If not as intended, make improvements.

2. Validate existing file-response evaluation.
   - Ensure the mode that scores pre-generated candidate JSONL files is present and correct.
   - Ensure imports are robust from the backend root, e.g. `from app.analytics.evaluator import ...`.
   - If not as intended, make improvements.

3. Add live evaluation only if it is missing.
   - Suggested CLI: `--mode file|live`.
   - For live mode, generate held-out synthetic crash dumps using `SatelliteFaultSimulator`.
   - Run `SentinelAgent.analyze_with_rag()` with mocked/stubbed calls in tests, real calls only when user explicitly runs evaluation with API keys.

4. Add ablation support carefully (if missing).
   - `--config full`: anomaly detector + RAG + safety.
   - `--config no-rag`: use fallback KB / no PDF RAG.
   - `--config no-safety`: bypass deterministic safety only if `agent.py` supports an explicit `skip_safety` flag.
   - `--config base-model`: baseline prompt with minimal/no domain system prompt.
   - Do not break the default demo path.

5. Validate metrics are honest and implemented correctly.
   - Keep fault-class accuracy.
   - Keep confidence calibration.
   - Keep recovery coverage.
   - Keep JSON validity.
   - Keep demo_scenario_success_rate.
   - Keep requires_human_review_correct.
   - Keep retry_malformed_rate.
   - Keep mean_latency_ms.
   - Add safety alignment only if the validation result is actually available.
   - Never write placeholder numbers into results.
   - If not as intended, make improvements.

6. Output Validation:
   - Check if evaluation scripts can write to `sentinel/backend/results/evaluation_results.json` and similar files.

Validation commands:

```bash
venv/bin/python -m pytest sentinel/backend/tests/test_schema_alignment.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_pipeline.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_rag.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_safety.py -q
```

If live evaluation requires `GEMINI_API_KEY`, do not fake success. Report that the code path is implemented but live numbers require the key.
```

---

# PROMPT 4 - ESA REAL TELEMETRY AND EARLY WARNING

```text
You are my coding assistant for SENTINEL.

Goal: integrate ESA-ADB honestly and add early-warning demo support.

Use these actual paths:

- ESA-Mission1/
- sentinel/backend/data_tools/esa_adb_crash_dump.py
- sentinel/backend/data/esa_crash_dumps/
- sentinel/docs/person1_esa_crash_dump_workflow.md
- sentinel/backend/app/analytics/anomaly_detector.py
- sentinel/backend/app/analytics/
- sentinel/backend/app/api/scenarios.py
- sentinel/frontend/src/App.jsx

ESA facts:

- `labels.csv` provides event ID, affected channel, start time, and end time.
- `anomaly_types.csv` provides category, class, subclass, dimensionality, locality, and length.
- `channels/channel_*.zip` contains real normalized telemetry streams.
- `telecommands/telecommand_*.zip` contains real anonymized command occurrence streams.
- Channel names and subsystem names are anonymized.
- There is no real root-cause label or recovery command label.

Tasks:

1. Verify or rebuild ESA crash-dump artifacts.
   - If `ESA-Mission1` exists, run summary/build through `data_tools/esa_adb_crash_dump.py`.
   - Do not fully unzip 9+ GB unless explicitly needed.
   - Prefer reading zipped pandas pickles directly.

Suggested commands:

```bash
PYTHONPATH=sentinel/backend venv/bin/python sentinel/backend/data_tools/esa_adb_crash_dump.py summary \
  --dataset ESA-Mission1 \
  --output sentinel/backend/data/esa_crash_dumps/mission1_summary.json

PYTHONPATH=sentinel/backend venv/bin/python sentinel/backend/data_tools/esa_adb_crash_dump.py build \
  --dataset ESA-Mission1 \
  --event-id id_109 \
  --output sentinel/backend/data/esa_crash_dumps/esa_mission1_id_109_crash_dump.json \
  --compact-output sentinel/backend/data/esa_crash_dumps/esa_mission1_id_109_sentinel_only.json
```

2. Add ESA scenario metadata to `app/api/scenarios.py` if missing.
   - Source type: `Real ESA Telemetry`.
   - Fault type can be `ESA_ADB_ANOMALY` or similar.
   - Include `operating_context.label_id`.
   - Do not map anonymized `channel_41` to ADCS/EPS/TCS unless explicitly known.

3. Add ESA integration tests.
   - Load `esa_mission1_id_109_sentinel_only.json`.
   - Mock the LLM response.
   - Verify the backend accepts the crash dump.
   - Verify output validates as `SentinelOutput`.
   - Verify the test does not claim root-cause accuracy on ESA.

4. Add early warning under package layout.
   - Preferred path: `sentinel/backend/app/analytics/early_warning.py`.
   - Use the existing z-score/anomaly detector where possible.
   - Output `EarlyWarningAlert` objects with:
     - warning offset
     - anomalous parameters
     - max z-score
     - suspected fault type
     - confidence
     - message

5. Early warning heuristic can map known synthetic parameters:
   - Gyro_rate_degs or SEU_counter -> ADCS_GYRO_SEU
   - V_bat, I_sa, or SoC_pct -> EPS_SOLAR_UNDERVOLT
   - CPU_load_pct or Watchdog_counter -> OBC_WATCHDOG_OVERFLOW
   - Component_temp_C or Heater_power_W -> TCS_THERMAL_RUNAWAY
   - Transponder_lock or SNR_dB -> COMMS_TRANSPONDER_LOSS
   - Otherwise -> MULTI_CASCADE with low confidence

6. Frontend:
   - Add a `Live Safe-Mode Stream` demo mode if not present.
   - Add real ESA incident presets.
   - Clearly distinguish `Real ESA Telemetry` from `Synthetic Safe Mode`.

Validation commands:

```bash
venv/bin/python -m pytest sentinel/backend/tests/test_pipeline.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_schema_alignment.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_rag.py -q
```

Add focused tests for ESA and early warning if they do not exist yet.
```

---

# PROMPT 5 - FINAL SYSTEM INTEGRATION AND DEMO RELIABILITY

```text
You are my coding assistant for SENTINEL.

Goal: final reliability pass for the hackathon demo.

Prerequisites:

- Prompt 0.5 completed.
- Prompt 1 schema/data/test alignment completed.
- Prompt 2 backend/frontend streaming completed.
- Prompt 3 evaluation path completed or explicitly blocked by missing API key.
- Prompt 4 ESA/early-warning integration completed.

Tasks:

1. Run backend test suite in the safest available form.
   - Use `pytest` for pytest-compatible files.
   - Run script-style files directly if they call `sys.exit()` at import time.

Suggested commands:

```bash
venv/bin/python -m pytest sentinel/backend/tests/test_schema_alignment.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_pipeline.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_generate_crash_dump.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_safety.py -q
venv/bin/python -m pytest sentinel/backend/tests/test_rag.py -q
venv/bin/python sentinel/backend/tests/test_models.py


2. Run demo scenario reliability.
   - Use three synthetic scenarios:
     - ADCS_GYRO_SEU
     - EPS_SOLAR_UNDERVOLT
     - OBC_WATCHDOG_OVERFLOW
   - Run each scenario 5 times if live LLM access is available.
   - If live LLM access is unavailable, run the path with a deterministic mocked LLM and clearly label it as mocked.

Pass criteria per run:

- Valid `SentinelOutput`.
- Rank-1 root cause matches the synthetic ground truth.
- Completed within 90 seconds.
- Recovery plan has at least 3 steps.
- Reasoning summary is non-empty.
- `requires_human_review` follows safety/confidence rules.

3. Generate cache files for demo fallback.

```text
sentinel/backend/data/demo_cache/gyro_seu_cached.json
sentinel/backend/data/demo_cache/solar_undervolt_cached.json
sentinel/backend/data/demo_cache/obc_watchdog_cached.json
```

These files should contain valid `SentinelOutput` JSON and enough trace metadata for the frontend to replay.

4. Verify frontend demo modes.
   - Live Safe-Mode Stream works.
   - Incident Library works.
   - Upload/Paste JSON works.
   - Source type is visible.
   - ESA examples do not claim confirmed root-cause/recovery labels.

5. Verify backend routes.
   - `GET /health`
   - `GET /api/health`
   - `GET /scenarios`
   - `GET /api/scenarios`
   - `POST /analyze`
   - `POST /api/analyze`

6. Produce final evidence files.
   - `sentinel/backend/results/evaluation_results.json` if real evaluation was run.
   - `sentinel/backend/results/demo_reliability.json`.
   - Screenshots or screen recording paths if frontend was manually verified.

7. Final pitch guardrails.
   - Do not say no autonomous recovery exists anywhere.
   - Say no existing system combines LLM-based causal reasoning, RAG over engineering procedures, safety validation, and auditable recovery generation for spacecraft safe-mode diagnosis.
   - Do not claim ESA data has root-cause labels.
   - Do not present fabricated accuracy or ablation numbers.

At the end, provide a concise readiness report:

- Tests passed.
- Demo modes verified.
- Live LLM evaluation status.
- Known risks.
- Exact next command to start backend.
- Exact next command to start frontend.
```

---

## Summary Table

| Prompt | Main Goal | Primary Files |
|---|---|---|
| 0.5 | Post-restructure contract audit | `sentinel/backend/app/*`, `sentinel/backend/simulation/*`, `sentinel/frontend/src/App.jsx` |
| 1 | Schema, prompt, generated labels, tests | `models.py`, `prompts.py`, `fault_simulator.py`, `dataset_generator.py`, `tests/`, `data/*.jsonl` |
| 2 | API streaming and frontend integration | `app/main.py`, `agent.py`, `api/models.py`, `frontend/src/App.jsx` |
| 3 | Evaluation and ablations | `app/analytics/evaluator.py`, `app/analytics/run_evaluation.py`, `agent.py` |
| 4 | ESA telemetry and early warning | `data_tools/esa_adb_crash_dump.py`, `data/esa_crash_dumps/`, `app/analytics/early_warning.py` |
| 5 | Demo reliability and submission hardening | backend tests, frontend demo, demo cache, results files |

## Current Leader Notes

The correct hackathon presentation is hybrid:

- Synthetic safe-mode incidents prove full root-cause and recovery-plan capability because they have labels.
- ESA-ADB incidents prove the system can ingest real spacecraft telemetry and anomaly labels.
- The live stream is the best frontend story.
- The incident library is the reliability fallback.
- Upload JSON is the judge-question escape hatch.
