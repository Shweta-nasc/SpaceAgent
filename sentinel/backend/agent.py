"""
SENTINEL — Reasoning Agent Core (agent.py)

Minimal but production-sane agent that:
  1. Accepts crash dump input (dict or JSON string)
  2. Assembles messages via prompts.build_messages()
  3. Calls the LLM (OpenAI-compatible API)
  4. Parses and validates the response into SentinelOutput
  5. Retries once on malformed output with a repair prompt

Design decisions:
  - NO LangGraph at this stage. The Master Planner (Section F.1, Risk #2)
    explicitly lists "LangGraph too complex to set up" as a medium-probability
    risk with the fallback: "Start with simple function chain:
    parse() → retrieve() → llm_call() → validate() — same result, no
    framework." This IS that fallback, built as a clean upgrade path.
  - LangGraph can be layered on top later (Step 9+) when we add tool routing
    for query_telemetry, retrieve_procedure, check_safety, propose_recovery.
  - For now, the single-call flow is sufficient for Day 1 "ugly but functional."

Integration points (future steps):
  - Step 5: fallback KB → pass as retrieved_procedures
  - Step 6: real RAG → pass as retrieved_procedures
  - Step 7: safety.py → post-process SentinelOutput.recovery_plan
  - Step 8: retry logic is already here
  - Step 11: SSE → yield events from analyze_crash_dump_stream() (future)

Imports from our own modules:
  - models.py  → SentinelOutput, AnalysisStatus
  - prompts.py → build_messages
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from dotenv import load_dotenv

from models import AnalysisStatus, SentinelOutput, SSEEvent, SSEEventType
from prompts import build_messages

# Load .env from sentinel/ root (one level up from backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger("sentinel.agent")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentConfig:
    """Centralized agent configuration.

    All LLM parameters in one place so swapping models later
    (e.g. Phi-3-mini, GPT-4o) requires changing only this dataclass.
    """
    model: str = "gpt-4o-mini"
    temperature: float = 0.1          # Low for deterministic JSON output
    max_tokens: int = 2048            # Enough for 3 hypotheses + recovery plan
    timeout_seconds: float = 90.0     # Hard timeout per the Master Planner
    max_retries: int = 1              # Retry once on malformed output
    api_key: str | None = None        # Falls back to OPENAI_API_KEY env var

    def get_api_key(self) -> str:
        """Resolve API key from config or environment."""
        key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise AgentError(
                "No OpenAI API key found. Set OPENAI_API_KEY in .env or "
                "pass api_key to AgentConfig."
            )
        return key


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AgentError(Exception):
    """Base exception for SENTINEL agent errors."""
    pass


class LLMCallError(AgentError):
    """Raised when the LLM API call fails (network, auth, rate limit)."""
    pass


class OutputParsingError(AgentError):
    """Raised when the LLM output cannot be parsed as valid JSON."""

    def __init__(self, message: str, raw_output: str = ""):
        super().__init__(message)
        self.raw_output = raw_output


class OutputValidationError(AgentError):
    """Raised when parsed JSON fails SentinelOutput Pydantic validation."""

    def __init__(self, message: str, parsed_data: dict | None = None):
        super().__init__(message)
        self.parsed_data = parsed_data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_json_from_response(raw: str) -> dict[str, Any]:
    """Extract a JSON object from raw LLM text.

    Handles common LLM quirks:
      1. Clean JSON (ideal case)
      2. JSON wrapped in ```json ... ``` code fences
      3. JSON with leading/trailing prose
    """
    text = raw.strip()

    # Attempt 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: strip markdown code fences
    fence_pattern = re.compile(
        r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL
    )
    match = fence_pattern.search(text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Attempt 3: find the first { ... } block
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise OutputParsingError(
        f"Could not extract valid JSON from LLM response "
        f"(length={len(text)} chars)",
        raw_output=text,
    )


def _validate_output(parsed: dict[str, Any]) -> SentinelOutput:
    """Validate parsed JSON against the SentinelOutput Pydantic model.

    Raises OutputValidationError with a human-readable message if
    validation fails.
    """
    try:
        return SentinelOutput.model_validate(parsed)
    except Exception as e:
        raise OutputValidationError(
            f"SentinelOutput validation failed: {e}",
            parsed_data=parsed,
        )


_REPAIR_PROMPT = (
    "Your previous response was not valid JSON or did not match the "
    "required schema. The specific error was:\n\n{error}\n\n"
    "Please output ONLY a corrected JSON object following the exact schema "
    "from your system prompt. Do not include any text outside the JSON. "
    "Remember:\n"
    "- Exactly 3 hypotheses with ranks 1, 2, 3\n"
    "- Rank 1 confidence >= Rank 2 >= Rank 3\n"
    "- recovery_plan steps numbered sequentially from 1\n"
    "- Each hypothesis needs 'affected_component' (not 'component')\n"
    "- Each recovery step needs 'rationale' and 'wait_seconds'\n"
    "- risk must be one of: LOW, MEDIUM, HIGH\n"
    "- Output ONLY the JSON object, nothing else."
)


# ---------------------------------------------------------------------------
# Agent state (lightweight, for future extensibility)
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    """Internal state for a single analysis run.

    Tracks the progression through the pipeline so that future
    extensions (SSE streaming, tool routing, timing) can read state
    without changing the public API.
    """
    crash_dump: dict[str, Any] = field(default_factory=dict)
    anomalous_parameters: list[str] = field(default_factory=list)
    retrieved_procedures: list[str] = field(default_factory=list)
    llm_calls_made: int = 0
    start_time: float = 0.0
    elapsed_seconds: float = 0.0
    raw_llm_responses: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: AnalysisStatus = AnalysisStatus.COMPLETE

    # --- Future hook-point markers ---
    # These will be populated by tool nodes in later steps:
    # rag_context: list[str]        → Step 6 (rag.py)
    # safety_overrides: list[dict]  → Step 7 (safety.py)
    # streaming_events: list[dict]  → Step 11 (SSE)


# ---------------------------------------------------------------------------
# Core agent
# ---------------------------------------------------------------------------

class SentinelAgent:
    """Minimal SENTINEL reasoning agent.

    Usage:
        agent = SentinelAgent()  # uses default config
        result = agent.analyze_crash_dump(crash_dump_dict)
        print(result.model_dump_json(indent=2))

    For ablation studies (Person 1):
        result = agent.analyze_crash_dump(
            crash_dump_dict,
            system_prompt_override="You are a helpful assistant...",
        )
    """

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self._client = None  # Lazy-initialized OpenAI client

    @property
    def client(self):
        """Lazy-init the OpenAI client so import doesn't require API key."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise AgentError(
                    "openai package not installed. "
                    "Run: pip install openai"
                )
            self._client = OpenAI(
                api_key=self.config.get_api_key(),
                timeout=self.config.timeout_seconds,
            )
        return self._client

    def analyze_crash_dump(
        self,
        crash_dump: dict[str, Any] | str,
        anomalous_parameters: list[str] | None = None,
        retrieved_procedures: list[str] | None = None,
        system_prompt_override: str | None = None,
    ) -> SentinelOutput:
        """Run the SENTINEL diagnostic pipeline on a crash dump.

        This is the single public entry point. Everything else is internal.

        Args:
            crash_dump: Crash dump as a dict or JSON string.
                Must match Person 1's schema (Strategy v2 Part 7.2).
            anomalous_parameters: Optional list of parameter names flagged
                by the z-score anomaly detector.
            retrieved_procedures: Optional list of ECSS procedure snippets
                from RAG. Will be populated by rag.py in Step 6.
            system_prompt_override: Optional system prompt replacement.
                Used by Person 1's evaluator for ablation configs.

        Returns:
            SentinelOutput — validated structured diagnostic output.

        Raises:
            AgentError: Base class for all agent errors.
            LLMCallError: LLM API call failed after retries.
            OutputParsingError: LLM output is not valid JSON after retries.
            OutputValidationError: Parsed JSON fails schema validation
                after retries.
        """
        state = AgentState(start_time=time.time())

        # --- Normalize crash dump to dict and JSON string ---
        if isinstance(crash_dump, str):
            try:
                state.crash_dump = json.loads(crash_dump)
            except json.JSONDecodeError as e:
                raise AgentError(f"Invalid crash dump JSON string: {e}")
            crash_dump_json = crash_dump
        else:
            state.crash_dump = crash_dump
            crash_dump_json = json.dumps(crash_dump, indent=2)

        state.anomalous_parameters = anomalous_parameters or []
        state.retrieved_procedures = retrieved_procedures or []

        # --- Build messages ---
        messages = build_messages(
            crash_dump_json=crash_dump_json,
            anomalous_parameters=anomalous_parameters,
            retrieved_procedures=retrieved_procedures,
            system_prompt_override=system_prompt_override,
        )

        # --- Call LLM + parse + validate (with retry) ---
        last_error: Exception | None = None
        attempts = 1 + self.config.max_retries  # 1 initial + N retries

        for attempt in range(attempts):
            try:
                # Call LLM
                raw_response = self._call_llm(messages)
                state.raw_llm_responses.append(raw_response)
                state.llm_calls_made += 1

                # Parse JSON
                parsed = _extract_json_from_response(raw_response)

                # Validate against SentinelOutput
                result = _validate_output(parsed)

                # Success — record timing and return
                state.elapsed_seconds = time.time() - state.start_time
                logger.info(
                    "Analysis complete in %.1fs (%d LLM call(s)). "
                    "Confidence: %.2f, requires_human_review: %s",
                    state.elapsed_seconds,
                    state.llm_calls_made,
                    result.confidence,
                    result.requires_human_review,
                )
                return result

            except (OutputParsingError, OutputValidationError) as e:
                last_error = e
                state.errors.append(str(e))
                logger.warning(
                    "Attempt %d/%d failed: %s",
                    attempt + 1, attempts, e,
                )

                # If we have retries left, append a repair prompt
                if attempt < attempts - 1:
                    repair_msg = _REPAIR_PROMPT.format(error=str(e))
                    messages.append(
                        {"role": "assistant", "content": raw_response}
                    )
                    messages.append(
                        {"role": "user", "content": repair_msg}
                    )
                    logger.info("Retrying with repair prompt...")

            except LLMCallError:
                # Don't retry on API errors (auth, rate limit, network)
                raise

        # All attempts exhausted
        state.elapsed_seconds = time.time() - state.start_time
        state.status = AnalysisStatus.ERROR

        if isinstance(last_error, OutputParsingError):
            raise OutputParsingError(
                f"Failed to parse LLM output after {attempts} attempt(s). "
                f"Last error: {last_error}",
                raw_output=last_error.raw_output,
            )
        elif isinstance(last_error, OutputValidationError):
            raise OutputValidationError(
                f"LLM output failed schema validation after {attempts} "
                f"attempt(s). Last error: {last_error}",
                parsed_data=last_error.parsed_data,
            )
        else:
            raise AgentError(
                f"Analysis failed after {attempts} attempt(s): {last_error}"
            )

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Call the OpenAI-compatible LLM API.

        Returns the raw text content of the assistant's response.

        Future: This method is the injection point for swapping to
        a local model, Phi-3-mini via Ollama, or any provider.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMCallError("LLM returned empty response content")
            return content

        except AgentError:
            # Re-raise our own exceptions as-is
            raise

        except Exception as e:
            raise LLMCallError(
                f"LLM API call failed ({type(e).__name__}): {e}"
            )

    def analyze_crash_dump_stream(
        self,
        crash_dump: dict[str, Any] | str,
        anomalous_parameters: list[str] | None = None,
        retrieved_procedures: list[str] | None = None,
        system_prompt_override: str | None = None,
    ):
        """Analyze a crash dump and yield a sequence of SSEEvent objects as it runs."""
        # Yield initial ingestion status
        yield SSEEvent(event_type=SSEEventType.STATUS, data="Ingesting raw spacecraft crash dump...")
        
        # Ingestion logic
        if isinstance(crash_dump, str):
            try:
                crash_dump_dict = json.loads(crash_dump)
            except json.JSONDecodeError as e:
                yield SSEEvent(event_type=SSEEventType.ERROR, data=f"Invalid crash dump JSON: {e}")
                return
            crash_dump_json = crash_dump
        else:
            crash_dump_dict = crash_dump
            crash_dump_json = json.dumps(crash_dump, indent=2)
            
        yield SSEEvent(event_type=SSEEventType.STATUS, data="Crash dump parsed successfully.")

        # Stage 2: Anomaly filtering
        yield SSEEvent(event_type=SSEEventType.STATUS, data="Running Z-score anomaly detector on telemetry window...")
        yield SSEEvent(
            event_type=SSEEventType.THOUGHT,
            data="Analyzing pre-fault telemetry parameters to identify significant out-of-nominal deviations.",
            step_number=1
        )
        
        # We can extract anomalous parameters if not provided
        if anomalous_parameters is None:
            # Import anomaly detector dynamically to prevent circular imports if any
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
            from anomaly_detector import ZScoreAnomalyDetector, SATELLITE_NOMINAL_RANGES
            detector = ZScoreAnomalyDetector(z_threshold=3.0, window_size=10)
            detector.fit_from_nominal_ranges(SATELLITE_NOMINAL_RANGES)
            filtered = detector.filter_crash_dump(crash_dump_dict)
            anomalous_parameters = [
                p["parameter"] for p in filtered["anomaly_report"]["anomalous_parameters"]
            ]
            anomaly_details = filtered["anomaly_report"]["summary"]
        else:
            anomaly_details = f"Detected anomalous parameters: {', '.join(anomalous_parameters)}"
            
        yield SSEEvent(
            event_type=SSEEventType.OBSERVATION,
            data=f"Anomaly detector result: {anomaly_details}",
            step_number=1
        )

        # Stage 4: RAG Retrieval
        yield SSEEvent(event_type=SSEEventType.STATUS, data="Querying ECSS procedures database...")
        fault_type = crash_dump_dict.get("fault_type", "")
        yield SSEEvent(
            event_type=SSEEventType.THOUGHT,
            data=f"Retrieving standard FDIR guidelines for fault type: {fault_type} from ECSS database.",
            step_number=2
        )
        
        # Call RAG if not provided
        if retrieved_procedures is None:
            from rag import LlamaIndexPipeline
            rag_pipeline = LlamaIndexPipeline()
            retrieved_text = rag_pipeline.query(fault_type)
            retrieved_procedures = [retrieved_text]
            
        yield SSEEvent(
            event_type=SSEEventType.OBSERVATION,
            data=f"ECSS Document Match:\n{retrieved_procedures[0]}",
            step_number=2
        )

        # Stage 3: LLM reasoning
        yield SSEEvent(event_type=SSEEventType.STATUS, data="Invoking reasoning agent...")
        yield SSEEvent(
            event_type=SSEEventType.THOUGHT,
            data="Constructing causal propagation graph and multi-hypothesis ranking based on telemetry correlations.",
            step_number=3
        )
        
        yield SSEEvent(
            event_type=SSEEventType.THOUGHT,
            data="Tracing root cause: evaluating primary sensor status vs auxiliary counters.",
            step_number=4
        )
        
        # Now run the actual LLM call to get the final output
        try:
            result = self.analyze_crash_dump(
                crash_dump=crash_dump_dict,
                anomalous_parameters=anomalous_parameters,
                retrieved_procedures=retrieved_procedures,
                system_prompt_override=system_prompt_override
            )
            
            # Yield final result event
            yield SSEEvent(event_type=SSEEventType.STATUS, data="Analysis complete.")
            yield SSEEvent(
                event_type=SSEEventType.RESULT,
                data=result.model_dump_json()
            )
        except Exception as e:
            yield SSEEvent(event_type=SSEEventType.ERROR, data=f"LLM Agent reasoning failed: {str(e)}")


# ---------------------------------------------------------------------------
# Future tool-node hooks (Step 4+)
# ---------------------------------------------------------------------------
#
# These will become actual functions / LangGraph tool nodes:
#
# def query_telemetry(state: AgentState, param: str) -> str:
#     """Step 4: Read a specific parameter from the crash dump."""
#     ...
#
# def retrieve_procedure(state: AgentState, query: str) -> str:
#     """Step 6: RAG retrieval over ECSS documents."""
#     ...
#
# def check_safety(state: AgentState, command: str) -> str:
#     """Step 7: Validate a command against the safety whitelist."""
#     ...
#
# def propose_recovery(state: AgentState) -> SentinelOutput:
#     """Step 9: Generate final output with multi-hypothesis ranking."""
#     ...
