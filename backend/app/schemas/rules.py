"""
Pydantic schemas for the Deterministic Rule Engine (Milestone M2).

Every rule check returns typed, structured outputs with:
- rule_id (HC-01 through HC-10, SP-01 through SP-04)
- constraint_type ("hard" | "soft")
- severity ("error" | "warning" | "info")
- message (human-readable explanation)
- affected_entity_ids (stable entity IDs)
- evidence_refs (typed evidence references for traceability)
- details (key-value structured data)
- signature (deterministic comparison hash for state diffing)
"""
from __future__ import annotations

import enum
import hashlib
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class SeverityEnum(str, enum.Enum):
    error = "error"
    warning = "warning"
    info = "info"


class ConstraintTypeEnum(str, enum.Enum):
    hard = "hard"
    soft = "soft"


class EvidenceRef(BaseModel):
    """Traceable reference to an entity or record in the system."""
    ref_type: str = Field(
        description="Type of entity: faculty, room, course, section, period, occurrence, leave"
    )
    ref_id: uuid.UUID | None = Field(
        default=None,
        description="ID of the referenced database record, or None for general rules"
    )
    description: str = Field(description="Evidence summary")


class Violation(BaseModel):
    """
    Structured violation emitted by a rule check.

    Matches SPEC.md Section 6:
        rule_id, severity, message, affected_entity_ids, evidence_refs, details
    """
    rule_id: str = Field(description="Identifier (e.g. HC-01, HC-02, SP-01)")
    constraint_type: ConstraintTypeEnum = Field(
        default=ConstraintTypeEnum.hard,
        description="Hard constraint (must not be violated) or soft preference"
    )
    severity: SeverityEnum = Field(default=SeverityEnum.error)
    message: str = Field(description="Human-readable explanation of the violation")
    affected_entity_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="IDs of affected entities (faculty, rooms, occurrences, etc.)"
    )
    evidence_refs: list[EvidenceRef] = Field(
        default_factory=list,
        description="Traceable references to evidence records"
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key-value context for algorithmic consumption"
    )
    signature: str = Field(
        default="",
        description="Deterministic signature for baseline-vs-proposed state diffing"
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.signature:
            # Deterministic signature based on rule_id + sorted affected entity IDs + key details
            sorted_entities = sorted(str(eid) for eid in self.affected_entity_ids)
            detail_keys = sorted(f"{k}:{v}" for k, v in self.details.items() if isinstance(v, (str, int, float, bool)))
            raw = f"{self.rule_id}|{'|'.join(sorted_entities)}|{'|'.join(detail_keys)}"
            self.signature = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class RuleValidationResult(BaseModel):
    """Complete outcome of running the rule engine against a schedule or simulation."""
    is_valid: bool = Field(description="True if zero hard constraint violations exist")
    total_violations: int = Field(default=0)
    hard_violations_count: int = Field(default=0)
    soft_violations_count: int = Field(default=0)
    violations: list[Violation] = Field(default_factory=list)
    by_rule: dict[str, list[Violation]] = Field(default_factory=dict)
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class ComparisonResult(BaseModel):
    """
    Comparison between baseline state and proposed state (HC-09).

    Reports:
    - existing_violations (in both baseline and proposed)
    - resolved_violations (in baseline, but eliminated in proposed)
    - new_violations (newly introduced in proposed)
    - remaining_violations (same as existing)
    """
    baseline_violations: list[Violation] = Field(default_factory=list)
    proposed_violations: list[Violation] = Field(default_factory=list)
    existing_violations: list[Violation] = Field(default_factory=list)
    resolved_violations: list[Violation] = Field(default_factory=list)
    new_violations: list[Violation] = Field(default_factory=list)
    remaining_violations: list[Violation] = Field(default_factory=list)
    introduces_new_hard_violations: bool = Field(
        description="True if any newly introduced violation is a hard constraint"
    )
    is_valid: bool = Field(
        description="True if zero new hard violations were introduced"
    )


class SoftPreferenceResult(BaseModel):
    """Evaluation result for a single soft preference (SP-01 to SP-04)."""
    preference_id: str
    name: str
    score: float = Field(ge=0.0, le=1.0, description="Normalized score [0.0, 1.0]")
    weight: float = Field(ge=0.0, le=1.0, description="Configured weight")
    weighted_score: float = Field(description="score * weight")
    details: dict[str, Any] = Field(default_factory=dict)
    explanation: str


class ConflictsResponse(BaseModel):
    """Response model for GET /conflicts endpoint."""
    is_valid: bool
    total_conflicts: int
    hard_conflicts: int
    soft_conflicts: int
    violations: list[Violation]
    by_rule: dict[str, list[Violation]]
    evaluation_scope: str = Field(description="Scope: 'template' or 'dated_occurrences'")
    target_date: date | None = None
    data_label: str = "SYNTHETIC — NOT REAL INSTITUTIONAL DATA"


class FacultyWorkloadDetail(BaseModel):
    faculty_id: uuid.UUID
    faculty_name: str
    employee_code: str
    department_code: str
    weekly_max_hours: float
    assigned_hours: float
    assigned_occurrences_count: int
    utilization_rate: float = Field(description="assigned_hours / weekly_max_hours")
    is_overloaded: bool


class WorkloadResponse(BaseModel):
    """Response model for GET /workload endpoint."""
    week_start: date
    week_end: date
    total_faculty: int
    overloaded_count: int
    avg_hours: float
    max_hours: float
    min_hours: float
    faculty_workloads: list[FacultyWorkloadDetail]
    data_label: str = "SYNTHETIC — NOT REAL INSTITUTIONAL DATA"

