"""
SENTINEL — Structured Output Contract (models.py)

This module defines the Pydantic schemas for SENTINEL's LLM agent output.
It is the single source of truth for the JSON shape that:
  - The LLM agent must produce (Person 2)
  - The FastAPI backend serializes over SSE (Person 4)
  - The React frontend renders (Person 3)
  - The evaluator scores against ground truth (Person 1)

Schema decisions are derived from:
  - SENTINEL_Hackathon_Strategy_v2.md Part 4.3 (system prompt output format)
  - SENTINEL_4Day_Master_Planner.md Section D (P2 deliverables)
  - ECSS-E-ST-70-11C safe mode recovery procedures
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SubsystemID(str, Enum):
    """Satellite subsystem identifiers used across all SENTINEL components."""
    ADCS = "ADCS"   # Attitude Determination & Control
    EPS = "EPS"     # Electrical Power System
    OBC = "OBC"     # On-Board Computer
    TCS = "TCS"     # Thermal Control System
    COMMS = "COMMS"  # Communications
    PYLD = "PYLD"   # Payload


class RiskLevel(str, Enum):
    """Risk classification for individual recovery steps."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"  # Safety validator blocked this command


class AnalysisStatus(str, Enum):
    """Overall status of the agent's analysis run."""
    COMPLETE = "complete"
    PARTIAL = "partial"    # Graceful degradation — some steps succeeded
    TIMEOUT = "timeout"    # Agent hit the hard 90-second limit
    ERROR = "error"        # Unrecoverable failure


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class RecoveryStep(BaseModel):
    """A single step in the recovery command sequence.

    Each step maps to a spacecraft command, its rationale, timing,
    verification criteria, and risk level.  The safety validator
    may override the risk to BLOCKED.
    """
    step: int = Field(..., ge=1, description="1-indexed step number")
    command: str = Field(
        ...,
        min_length=3,
        description="Spacecraft command name, e.g. CMD_GYRO_A_DRIVER_RESET",
    )
    rationale: str = Field(
        ...,
        min_length=5,
        description="Why this command is issued at this point in the sequence",
    )
    wait_seconds: int = Field(
        ...,
        ge=0,
        description="Seconds to wait after issuing command before verifying",
    )
    verify: str = Field(
        ...,
        min_length=3,
        description="Condition to check after wait, e.g. 'GYRO_A_RATE returns valid'",
    )
    risk: RiskLevel = Field(
        ...,
        description="Risk level of this step (LOW / MEDIUM / HIGH / BLOCKED)",
    )


class Hypothesis(BaseModel):
    """A single ranked diagnosis hypothesis.

    The agent MUST always produce exactly 3 hypotheses.
    Even for obvious faults: H1 (high confidence), H2 and H3 (low).
    This enables multi-hypothesis reasoning and graceful degradation
    when the top hypothesis is wrong.
    """
    rank: int = Field(..., ge=1, le=3, description="Rank 1 = most likely")
    root_cause: str = Field(
        ...,
        min_length=3,
        description="Fault class, e.g. EPS_POWER_FAULT, ADCS_GYRO_SEU",
    )
    component: str = Field(
        ...,
        min_length=2,
        description="Affected component, e.g. SOLAR_ARRAY_A, GYRO_A",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in this hypothesis (0.0–1.0)",
    )
    causal_chain: List[str] = Field(
        ...,
        min_length=2,
        description=(
            "Ordered list of events from trigger to safe mode, "
            "e.g. ['I_sa drops to 0A', 'V_bat falls to 24V', 'EPS fault flag set']"
        ),
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Keep confidence to 2 decimal places for clean display."""
        return round(v, 2)


class SentinelOutput(BaseModel):
    """Top-level structured output from the SENTINEL agent.

    This is the exact JSON shape that:
      - The LLM must return (via system prompt enforcement + retry)
      - The FastAPI endpoint serializes
      - The React frontend destructures
      - The evaluator compares to ground truth

    Contract invariants:
      1. Exactly 3 hypotheses, ranked 1-2-3
      2. Hypothesis confidences are descending (rank 1 ≥ rank 2 ≥ rank 3)
      3. requires_human_review is True when overall confidence < 0.70
         OR any recovery step has risk HIGH or BLOCKED
      4. recovery_plan has at least 1 step
      5. Overall confidence matches hypothesis rank-1 confidence
    """

    hypotheses: List[Hypothesis] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 ranked diagnostic hypotheses",
    )
    recovery_plan: List[RecoveryStep] = Field(
        ...,
        min_length=1,
        description="Ordered recovery command sequence for the top hypothesis",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence (should equal top-hypothesis confidence)",
    )
    requires_human_review: bool = Field(
        ...,
        description=(
            "True when confidence < 0.70 or any step is HIGH/BLOCKED risk"
        ),
    )
    reasoning_summary: str = Field(
        ...,
        min_length=10,
        description="2–4 sentence summary of the diagnostic reasoning chain",
    )
    status: AnalysisStatus = Field(
        default=AnalysisStatus.COMPLETE,
        description="Analysis completion status",
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 2)

    @model_validator(mode="after")
    def validate_output_invariants(self) -> "SentinelOutput":
        """Enforce the contract invariants documented above."""

        # --- Invariant 1: ranks must be exactly {1, 2, 3} ---
        ranks = sorted(h.rank for h in self.hypotheses)
        if ranks != [1, 2, 3]:
            raise ValueError(
                f"Hypotheses must have ranks [1, 2, 3], got {ranks}"
            )

        # --- Invariant 2: confidences must be non-increasing by rank ---
        sorted_by_rank = sorted(self.hypotheses, key=lambda h: h.rank)
        for i in range(len(sorted_by_rank) - 1):
            if sorted_by_rank[i].confidence < sorted_by_rank[i + 1].confidence:
                raise ValueError(
                    f"Hypothesis rank {sorted_by_rank[i].rank} confidence "
                    f"({sorted_by_rank[i].confidence}) must be >= rank "
                    f"{sorted_by_rank[i+1].rank} confidence "
                    f"({sorted_by_rank[i+1].confidence})"
                )

        # --- Invariant 3: auto-set requires_human_review ---
        has_high_risk = any(
            s.risk in (RiskLevel.HIGH, RiskLevel.BLOCKED)
            for s in self.recovery_plan
        )
        should_flag = self.confidence < 0.70 or has_high_risk
        if should_flag and not self.requires_human_review:
            # Auto-correct rather than reject — safer for hackathon reliability
            object.__setattr__(self, "requires_human_review", True)

        # --- Invariant 5: overall confidence matches rank-1 ---
        top_hyp = next(h for h in self.hypotheses if h.rank == 1)
        if abs(self.confidence - top_hyp.confidence) > 0.01:
            # Auto-correct to top hypothesis confidence
            object.__setattr__(self, "confidence", top_hyp.confidence)

        return self


# ---------------------------------------------------------------------------
# SSE event wrapper (used by Person 4's streaming endpoint)
# ---------------------------------------------------------------------------

class SSEEventType(str, Enum):
    """Event types streamed over SSE to the frontend."""
    THOUGHT = "thought"         # Agent reasoning step
    ACTION = "action"           # Tool call initiated
    OBSERVATION = "observation"  # Tool call result
    RESULT = "result"           # Final SentinelOutput
    ERROR = "error"             # Error message
    STATUS = "status"           # Progress updates


class SSEEvent(BaseModel):
    """A single SSE event sent from backend to frontend.

    Person 3 uses `event_type` to route data to the correct UI panel:
      - THOUGHT/ACTION/OBSERVATION → Panel 2 (Reasoning Trace)
      - RESULT → Panel 3 (Causal DAG) + Panel 4 (Recovery Plan)
      - ERROR → Error toast
      - STATUS → Header status indicator
    """
    event_type: SSEEventType
    data: str = Field(
        ...,
        description="Payload — plain text for trace events, JSON for RESULT",
    )
    step_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Agent reasoning step index (for trace events)",
    )
