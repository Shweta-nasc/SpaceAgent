# SENTINEL Post-Prompt-0 Audit Report

> **Date:** 2026-06-14 · **Status:** ✅ ALL CLEAR — Prompts 1–5 can proceed safely

---

## 1. Active Source Tree

```
sentinel/
├── .env                                    # GEMINI_API_KEY
├── .env.example
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── prepare_upload.py
│   ├── app/                                # ← Active backend code
│   │   ├── __init__.py
│   │   ├── main.py                         # FastAPI app (routes)
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py                    # SentinelAgent (33.9 KB)
│   │   │   ├── prompts.py                  # FAULT_SIGNATURES + system prompt
│   │   │   ├── rag.py                      # PDF RAG + fallback KB
│   │   │   └── safety.py                   # Deterministic whitelist validator
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── models.py                   # Pydantic schemas (SentinelOutput, SSEEvent, CrashDumpRequest)
│   │   │   └── scenarios.py                # Preset demo crash dumps
│   │   └── analytics/
│   │       ├── __init__.py
│   │       ├── anomaly_detector.py         # Z-score anomaly detection
│   │       ├── evaluator.py                # GROUND_TRUTH_REGISTRY + scoring
│   │       ├── run_evaluation.py           # JSONL evaluation runner
│   │       └── scorecard.py                # Metric aggregation
│   ├── simulation/                         # ← Active simulation code
│   │   ├── __init__.py
│   │   ├── fault_simulator.py              # SatelliteFaultSimulator (54.4 KB)
│   │   ├── dataset_generator.py            # JSONL training data generator
│   │   └── simulator.py                    # Legacy wrapper
│   ├── data/
│   │   ├── sentinel_training.jsonl         # Generated training data
│   │   ├── train.jsonl                     # Train split
│   │   ├── valid.jsonl                     # Validation split
│   │   └── ecss/                           # ECSS PDF documents for RAG
│   ├── data_tools/
│   │   └── esa_adb_crash_dump.py           # ESA ADB crash dump generator ✅
│   └── tests/
│       ├── conftest.py                     # sys.path setup
│       ├── test_schema_alignment.py        # Canonical name validation (53 tests)
│       ├── test_generate_crash_dump.py     # Simulator correctness (42 tests)
│       ├── test_models.py                  # Pydantic schema (18 tests)
│       ├── test_pipeline.py                # End-to-end pipeline (10 tests)
│       ├── test_safety.py                  # Safety validator (311 tests)
│       ├── test_prompts.py                 # Prompt template (108 tests)
│       ├── test_agent.py                   # Agent logic (68 tests)
│       ├── test_rag.py                     # RAG integration
│       ├── test_constructor.py             # Constructor tests
│       └── test_helpers.py                 # Helper utilities
├── docs/
│   └── person1_esa_crash_dump_workflow.md
├── frontend/
│   └── src/
│       ├── App.jsx                         # React dashboard
│       ├── App.css                         # Styling
│       └── index.jsx                       # Entry point
└── notebooks/
```

> [!IMPORTANT]
> Active backend code lives in `sentinel/backend/app/` and `sentinel/backend/simulation/` — confirmed. No stale `.py` files remain in the `sentinel/backend/` root (only `prepare_upload.py`).

---

## 2. ESA ADB Crash Dump Script

| Check | Result |
|---|---|
| `sentinel/backend/data_tools/esa_adb_crash_dump.py` exists | ✅ (27,745 bytes) |
| Source file (not just `__pycache__`) | ✅ Source `.py` file present |

No restoration needed.

---

## 3. Stale Label Scan

### Search scope: all `.py` files under `sentinel/backend/`

| Old Name | Hits in `app/` | Hits in `simulation/` | Hits in `tests/` | Verdict |
|---|---|---|---|---|
| `EPS_POWER_FAULT` | 0 | 0 | 1 | ✅ Intentional negative test |
| `ADCS_SENSOR_FAULT` | 0 | 0 | 2 | ✅ Intentional negative test |
| `OBC_SOFTWARE_FAULT` | 0 | 0 | 1 | ✅ Intentional negative test |
| `TCS_THERMAL_FAULT` | 0 | 0 | 1 | ✅ Intentional negative test |
| `COMMS_FAULT` | 0 | 0 | 1 | ✅ Intentional negative test |
| `MULTI_SYSTEM_CASCADE` | 0 | 0 | 2 | ✅ Intentional negative test |

All 8 hits are in [test_schema_alignment.py](file:///Users/nitishbiswas/Documents/GitHub/SpaceAgent/sentinel/backend/tests/test_schema_alignment.py) in the `OLD_NAMES` list (line 35–42) and `TestNoOldNamesInSimulator` / `TestEvaluatorScoresCorrectName::test_old_name_scores_false`. These are **intentional negative assertions** that verify old names are rejected.

| Frontend (`*.jsx`) | `data_tools/` | JSONL data files |
|---|---|---|
| 0 hits | 0 hits | 0 hits |

> [!TIP]
> Zero stale labels in production code. All occurrences are in negative test assertions.

---

## 4. JSONL Schema Validation

| File | `"component"` count | `"affected_component"` present | Stale fault names |
|---|---|---|---|
| `sentinel_training.jsonl` | **0** | ✅ Yes | **0** |
| `train.jsonl` | **0** | ✅ Yes | **0** |
| `valid.jsonl` | **0** | ✅ Yes | **0** |

Sample hypothesis from `sentinel_training.jsonl`:
```
Keys: ['affected_component', 'causal_chain', 'confidence', 'rank', 'root_cause']
root_cause: MULTI_CASCADE ← canonical name
```

`dataset_generator.py` also generates `"affected_component"` (lines 273, 280, 291). No stale `"component"` key anywhere.

---

## 5. SSE Contract Alignment

### Frontend expects (App.jsx line 257):
```javascript
const { event_type, data, step_number } = event;
```

### Backend emits (models.py lines 289–307):
```python
class SSEEvent(BaseModel):
    event_type: SSEEventType   # ✅ matches
    data: str                   # ✅ matches
    step_number: Optional[int]  # ✅ matches
```

### Event type enum values match frontend switch cases:
| Backend `SSEEventType` | Frontend `case` | Match |
|---|---|---|
| `"thought"` | `"thought"` | ✅ |
| `"action"` | `"action"` | ✅ |
| `"observation"` | `"observation"` | ✅ |
| `"result"` | `"result"` | ✅ |
| `"error"` | `"error"` | ✅ |
| `"status"` | `"status"` | ✅ |

> [!NOTE]
> The frontend also handles the `result.data` field correctly — it parses JSON from the string and destructures `hypotheses`, `recovery_plan`, `requires_human_review`, `reasoning_summary`, and `affected_component` from each hypothesis.

---

## 6. Route Verification

| Route | Method | Present | Source |
|---|---|---|---|
| `/health` | GET | ✅ | main.py:50 |
| `/api/health` | GET | ✅ | main.py:51 |
| `/scenarios` | GET | ✅ | main.py:57 |
| `/api/scenarios` | GET | ✅ | main.py:58 |
| `/api/analyze` | GET | ✅ | main.py:64 (EventSource for index.html) |
| `/analyze` | POST | ✅ | main.py:157 |
| `/api/analyze` | POST | ✅ | main.py:158 |

All 7 routes confirmed.

---

## 7. Test Results

| Test Suite | Runner | Result |
|---|---|---|
| `test_schema_alignment.py` | pytest | **53 passed** ✅ |
| `test_pipeline.py` | pytest | **10 passed** ✅ |
| `test_generate_crash_dump.py` | pytest | **42 passed** (130 subtests) ✅ |
| `test_models.py` | standalone | **18 passed** ✅ |
| `test_safety.py` | standalone | **311 passed** ✅ |
| `test_prompts.py` | standalone | **108 passed** ✅ |
| `test_agent.py` | standalone | **68 passed** ✅ |
| **Total** | | **610 passed, 0 failed** |

---

## 8. Verdict: Can Prompts 1–5 Run Safely?

### ✅ YES — All clear.

| Gate | Status |
|---|---|
| Source tree restructured correctly | ✅ |
| `esa_adb_crash_dump.py` source exists | ✅ |
| No stale fault labels in production code | ✅ |
| JSONL uses `affected_component`, not `component` | ✅ |
| SSE contract aligned between backend and frontend | ✅ |
| All 7 API routes registered | ✅ |
| All 610 tests pass | ✅ |
| No contract mismatches found requiring fixes | ✅ |

> [!IMPORTANT]
> **No code changes were needed.** The Prompt 0 restructuring was done correctly. Prompts 1–5 can proceed without risk of schema mismatches, import failures, or stale label collisions.
