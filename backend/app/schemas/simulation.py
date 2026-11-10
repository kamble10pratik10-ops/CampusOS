"""
Pydantic schemas for What-If Simulation, Independent Critic, and Audit (Milestone M4).

Matches SPEC.md Sections 8, 9, 11:
- Non-mutating what-if simulation pipeline
- Independent Critic with structured issue codes and multi-state status
- Before-and-after violation comparison
- Immutable audit record schemas
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import DecisionStatusEnum
from app.schemas.planner import AssignmentProposal, OptimizationPlan
from app.schemas.rules import ComparisonResult, EvidenceRef, SeverityEnum, Violation


class CriticStatusEnum(str, enum.Enum):
    feasible_complete = "feasible_complete"    # 100% coverage, all hard rules met
    feasible_partial = "feasible_partial"      # < 100% coverage, valid without new hard violations
    infeasible = "infeasible"                  # 0% coverage or solver failed
    validation_failed = "validation_failed"    # Proposed plan introduces new hard violations
    insufficient_data = "insufficient_data"    # Missing critical input data or records


class CriticIssue(BaseModel):
    """Structured issue emitted by the Independent Critic."""
    issue_code: str = Field(description="Deterministic issue code (e.g. CRITIC-ERR-NEW-HARD-VIOLATION)")
    severity: SeverityEnum
    message: str = Field(description="Human-readable explanation of the issue")
    details: dict[str, Any] = Field(default_factory=dict)


class CriticResult(BaseModel):
    """Outcome of the Independent Critic validation stage."""
    status: CriticStatusEnum
    is_approved: bool = Field(description="True if zero hard errors and plan is operationally valid")
    issues: list[CriticIssue] = Field(default_factory=list)
    claims_verified: bool = Field(description="True if claimed coverage count and scores match computed reality")
    new_hard_violations_count: int = Field(default=0)
    resolved_violations_count: int = Field(default=0)
    summary: str


class SimulationRequest(BaseModel):
    """Request payload to initiate a non-mutating what-if simulation."""
    scenario_name: str = Field(
        default="Faculty Absence What-If",
        description="Descriptive title for the simulation"
    )
    faculty_id: uuid.UUID | None = Field(
        default=None,
        description="Faculty member needing replacement (e.g. hero Dr. Raj Sharma)"
    )
    start_date: date | None = Field(
        default=None,
        description="Start date of absence"
    )
    end_date: date | None = Field(
        default=None,
        description="End date of absence"
    )
    occurrence_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Explicit class occurrence IDs to simulate replacements for"
    )
    custom_weights: dict[str, float] | None = Field(
        default=None,
        description="Optional custom preference weights for SP-01 to SP-04"
    )
    max_alternatives: int = Field(default=3, ge=1, le=5)


class SimulationResponse(BaseModel):
    """Comprehensive output of the non-mutating what-if simulation."""
    decision_id: uuid.UUID = Field(description="Immutable audit ID in decision table")
    scenario_summary: str
    scenario_parameters: dict[str, Any]
    critic_status: CriticStatusEnum
    affected_occurrences_count: int
    affected_occurrences: list[AssignmentProposal]
    baseline_conflicts_count: int
    baseline_violations: list[Violation]
    alternatives: list[OptimizationPlan]
    selected_plan: OptimizationPlan | None
    baseline_greedy_plan: OptimizationPlan | None
    diff: ComparisonResult
    critic_result: CriticResult
    evidence_refs: list[EvidenceRef]
    limitations: list[str] = Field(
        default_factory=list,
        description="Warnings regarding data limits or assumptions"
    )
    solver_status: str
    llm_status: str = "bypassed_deterministic"
    created_at: datetime
    created_by_email: str
    decision_status: DecisionStatusEnum = DecisionStatusEnum.simulation
    data_label: str = "SYNTHETIC — NOT REAL INSTITUTIONAL DATA"


class AuditListItem(BaseModel):
    """Summary of an audit record for list display."""
    model_config = {"from_attributes": True}

    id: uuid.UUID
    scenario_summary: str
    decision_status: DecisionStatusEnum
    critic_status: str
    coverage_percentage: float
    total_affected: int
    created_at: datetime
    created_by_email: str
    runtime_ms: int | None = None

