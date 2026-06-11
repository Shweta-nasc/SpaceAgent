"""
SENTINEL — Reasoning Agent Core (agent.py)

Gemini-first, model-agnostic reasoning agent that:
  1. Accepts crash dump input (dict or JSON string)
  2. Assembles messages via prompts.build_messages()
  3. Calls the LLM (Gemini Flash by default, with tuned and fallback branches)
  4. Parses and validates the response into SentinelOutput
  5. Retries once on malformed output with a repair prompt

Architecture — Three reasoning modes in one agent:
  - "base"    → Gemini Flash (hosted, fast, primary demo path)
  - "tuned"   → Tuned Gemini model or fine-tuned endpoint (more stable
                 repeated fault diagnosis, evaluation comparison)
  - "fallback"→ Local/open model via OpenAI-compatible API
                 (Phi-3-mini, Qwen2.5, Ollama, etc.)

The mode is set via AgentConfig.mode. All three modes share the same
pipeline: build_messages → call_llm → parse_json → validate. Only the
LLM call layer changes per mode. This keeps the architecture simple
and the demo safe.

Design decisions:
  - NO LangGraph at this stage. The Master Planner (Section F.1, Risk #2)
    explicitly lists "LangGraph too complex to set up" as a medium-probability
    risk with the fallback: "Start with simple function chain:
    parse() → retrieve() → llm_call() → validate() — same result, no
    framework." This IS that fallback, built as a clean upgrade path.
  - LangGraph can be layered on top later (Step 9+) when we add tool routing
    for query_telemetry, retrieve_procedure, check_safety, propose_recovery.

Integration points (future steps):
  - Step 4: fallback KB → pass as retrieved_procedures
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
from enum import Enum
from typing import Any, Optional

from dotenv import load_dotenv

from models import AnalysisStatus, SentinelOutput
from prompts import build_messages

# Load .env from sentinel/ root (one level up from backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger("sentinel.agent")


# ---------------------------------------------------------------------------
# Model mode enum
# ---------------------------------------------------------------------------

class ModelMode(str, Enum):
    """Selectable reasoning mode for the agent.

    All three modes use the same pipeline. Only the LLM call differs.
    """
    BASE = "base"          # Gemini Flash — primary hosted path
    TUNED = "tuned"        # Tuned Gemini model / fine-tuned endpoint
    FALLBACK = "fallback"  # Local/open model (Phi-3-mini, Qwen2.5, Ollama)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentConfig:
    """Centralized agent configuration.

    All LLM parameters in one place so swapping models later
    (e.g. Phi-3-mini, tuned Gemini) requires changing only this dataclass.

    Architecture:
      mode="base"     → uses Gemini Flash via google-genai
      mode="tuned"    → uses tuned_model_id via Gemini API (same client)
      mode="fallback" → uses fallback_model via OpenAI-compatible API
                         (Ollama, vLLM, any local server)
    """
    mode: ModelMode = ModelMode.BASE

    # --- Gemini (base + tuned) ---
    model: str = "gemini-2.5-flash"       # Primary hosted model
    tuned_model_id: str = ""              # e.g. "tunedModels/sentinel-v1"
    gemini_api_key: str | None = None     # Falls back to GEMINI_API_KEY env

    # --- Fallback (local/open model) ---
    fallback_model: str = "phi-3-mini"    # Model name for local server
    fallback_base_url: str = "http://localhost:11434/v1"  # Ollama default
    fallback_api_key: str = "ollama"      # Ollama doesn't need a real key

    # --- Shared LLM parameters ---
    temperature: float = 0.1              # Low for deterministic JSON output
    max_tokens: int = 2048                # Enough for 3 hypotheses + recovery
    timeout_seconds: float = 90.0         # Hard timeout per Master Planner
    max_retries: int = 1                  # Retry once on malformed output

    def get_gemini_api_key(self) -> str:
        """Resolve Gemini API key from config or environment."""
        key = self.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise AgentError(
                "No Gemini API key found. Set GEMINI_API_KEY in .env or "
                "pass gemini_api_key to AgentConfig."
            )
        return key

    @property
    def active_model_name(self) -> str:
        """Return the model name currently in use, for logging."""
        if self.mode == ModelMode.TUNED and self.tuned_model_id:
            return self.tuned_model_id
        if self.mode == ModelMode.FALLBACK:
            return self.fallback_model
        return self.model


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
    model_mode_used: str = ""

    # --- Future hook-point markers ---
    # These will be populated by tool nodes in later steps:
    # rag_context: list[str]        → Step 6 (rag.py)
    # safety_overrides: list[dict]  → Step 7 (safety.py)
    # streaming_events: list[dict]  → Step 11 (SSE)


# ---------------------------------------------------------------------------
# Core agent
# ---------------------------------------------------------------------------

class SentinelAgent:
    """SENTINEL reasoning agent — Gemini-first, model-agnostic.

    Supports three reasoning modes in one agent:
      - base:     Gemini Flash (primary demo path)
      - tuned:    Tuned Gemini model (more stable for repeated faults)
      - fallback: Local/open model via Ollama/vLLM (offline backup)

    Usage:
        agent = SentinelAgent()  # uses Gemini Flash by default
        result = agent.analyze_crash_dump(crash_dump_dict)
        print(result.model_dump_json(indent=2))

    Tuned model usage:
        config = AgentConfig(mode=ModelMode.TUNED,
                             tuned_model_id="tunedModels/sentinel-v1")
        agent = SentinelAgent(config)

    Fallback (local Phi-3-mini via Ollama):
        config = AgentConfig(mode=ModelMode.FALLBACK)
        agent = SentinelAgent(config)

    For ablation studies (Person 1):
        result = agent.analyze_crash_dump(
            crash_dump_dict,
            system_prompt_override="You are a helpful assistant...",
        )
    """

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self._gemini_client = None   # Lazy-initialized Gemini client
        self._fallback_client = None  # Lazy-initialized fallback client

    @property
    def gemini_client(self):
        """Lazy-init the Gemini client so import doesn't require API key."""
        if self._gemini_client is None:
            try:
                from google import genai
            except ImportError:
                raise AgentError(
                    "google-genai package not installed. "
                    "Run: pip install google-genai"
                )
            self._gemini_client = genai.Client(
                api_key=self.config.get_gemini_api_key(),
            )
        return self._gemini_client

    @property
    def fallback_client(self):
        """Lazy-init an OpenAI-compatible client for local/open models.

        Works with Ollama, vLLM, LM Studio, or any server that exposes
        an OpenAI-compatible /v1/chat/completions endpoint.
        """
        if self._fallback_client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise AgentError(
                    "openai package not installed (needed for fallback mode). "
                    "Run: pip install openai"
                )
            self._fallback_client = OpenAI(
                base_url=self.config.fallback_base_url,
                api_key=self.config.fallback_api_key,
                timeout=self.config.timeout_seconds,
            )
        return self._fallback_client

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
                from RAG. Will be populated by rag.py.
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
        state = AgentState(
            start_time=time.time(),
            model_mode_used=self.config.mode.value,
        )

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
                # Call LLM (provider-aware, mode-aware)
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
                    "Analysis complete in %.1fs (%d LLM call(s), mode=%s, "
                    "model=%s). Confidence: %.2f, requires_human_review: %s",
                    state.elapsed_seconds,
                    state.llm_calls_made,
                    self.config.mode.value,
                    self.config.active_model_name,
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
        """Call the LLM based on the configured mode.

        Routes to the appropriate provider:
          - base/tuned → Gemini API via google-genai
          - fallback   → OpenAI-compatible API (Ollama, vLLM, etc.)

        Returns the raw text content of the assistant's response.
        """
        if self.config.mode == ModelMode.FALLBACK:
            return self._call_fallback(messages)
        return self._call_gemini(messages)

    def _call_gemini(self, messages: list[dict[str, str]]) -> str:
        """Call Gemini API (base or tuned mode).

        Uses the google-genai client with generate_content.
        Handles both base Gemini Flash and tuned model endpoints.
        """
        try:
            # Select model: tuned model ID or base model
            if (self.config.mode == ModelMode.TUNED
                    and self.config.tuned_model_id):
                model_id = self.config.tuned_model_id
            else:
                model_id = self.config.model

            # Convert messages to Gemini format
            # Gemini uses system_instruction + contents
            system_text = None
            contents = []
            for msg in messages:
                if msg["role"] == "system":
                    system_text = msg["content"]
                elif msg["role"] == "user":
                    contents.append(msg["content"])
                elif msg["role"] == "assistant":
                    # For retry flow: include previous assistant response
                    contents.append(msg["content"])

            # Build config
            from google.genai import types
            gen_config = types.GenerateContentConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
                system_instruction=system_text,
            )

            response = self.gemini_client.models.generate_content(
                model=model_id,
                contents=contents,
                config=gen_config,
            )

            content = response.text
            if not content:
                raise LLMCallError("Gemini returned empty response content")
            return content

        except AgentError:
            raise

        except Exception as e:
            raise LLMCallError(
                f"Gemini API call failed ({type(e).__name__}): {e}"
            )

    def _call_fallback(self, messages: list[dict[str, str]]) -> str:
        """Call a local/open model via OpenAI-compatible API.

        Works with Ollama, vLLM, LM Studio, or any server that exposes
        an OpenAI-compatible /v1/chat/completions endpoint.

        This enables offline demo, Phi-3-mini experimentation, and
        model-agnostic evaluation without changing the pipeline.
        """
        try:
            response = self.fallback_client.chat.completions.create(
                model=self.config.fallback_model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMCallError(
                    "Fallback LLM returned empty response content"
                )
            return content

        except AgentError:
            raise

        except Exception as e:
            raise LLMCallError(
                f"Fallback LLM call failed ({type(e).__name__}): {e}"
            )


# ---------------------------------------------------------------------------
# Future tool-node hooks
# ---------------------------------------------------------------------------
#
# These will become actual functions / LangGraph tool nodes:
#
# def query_telemetry(state: AgentState, param: str) -> str:
#     """Read a specific parameter from the crash dump."""
#     ...
#
# def retrieve_procedure(state: AgentState, query: str) -> str:
#     """RAG retrieval over ECSS documents via rag.py."""
#     ...
#
# def check_safety(state: AgentState, command: str) -> str:
#     """Validate a command against the safety whitelist."""
#     ...
#
# def propose_recovery(state: AgentState) -> SentinelOutput:
#     """Generate final output with multi-hypothesis ranking."""
#     ...
#
# Future Step: add SSE streaming wrapper for analyze_crash_dump
# Future Step: auto-route to tuned model for repeated fault classes
# Future Step: add cached demo fallback for offline/rate-limited scenarios
