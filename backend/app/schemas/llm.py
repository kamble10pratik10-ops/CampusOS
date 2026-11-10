"""
Pydantic schemas for LLM interface, intent parsing, and natural language queries (M6).
"""
from __future__ import annotations

import enum
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.rules import ConflictsResponse, WorkloadResponse
from app.schemas.simulation import SimulationResponse


class IntentTypeEnum(str, enum.Enum):
    leave_simulation = "leave_simulation"
    check_conflicts = "check_conflicts"
    check_workload = "check_workload"
    clarification_needed = "clarification_needed"
    general_query = "general_query"


class ParsedIntent(BaseModel):
    """Structured intent parsed from natural language."""
    intent_type: IntentTypeEnum
    faculty_name_or_code: str | None = None
    faculty_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    department_code: str | None = None
    department_id: uuid.UUID | None = None
    max_alternatives: int = 3
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    missing_fields: list[str] = Field(default_factory=list)
    clarification_prompt: str | None = None
    raw_query: str


class ExplanationRequest(BaseModel):
    """Input payload for generating a readable explanation of a computed decision."""
    scenario_name: str
    faculty_name: str
    start_date: date
    end_date: date
    covered_occurrences: int
    total_occurrences: int
    coverage_percentage: float
    critic_status: str
    critic_summary: str
    new_hard_violations_count: int
    resolved_violations_count: int
    overall_score: float
    workload_shifts: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    """Request payload for POST /query natural language endpoint."""
    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question or operational scenario description.",
        examples=[
            "Dr. Raj Sharma is on leave next week Monday to Wednesday. Recommend replacement plans.",
            "What operational conflicts currently exist in Computer Science?",
            "Show faculty workload and overloaded teachers for next week.",
        ],
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional client context such as default department or selected dates.",
    )


class QueryResponse(BaseModel):
    """Response payload for POST /query natural language endpoint."""
    query: str
    parsed_intent: ParsedIntent
    explanation: str
    simulation: SimulationResponse | None = None
    conflicts: ConflictsResponse | None = None
    workload: WorkloadResponse | None = None
    llm_provider: str
    llm_model: str | None = None
    llm_status: str
    data_label: str = "SYNTHETIC — NOT REAL INSTITUTIONAL DATA"

