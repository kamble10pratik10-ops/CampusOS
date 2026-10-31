"""
Pydantic schemas for the dashboard endpoint.

NOTE (M1): conflict_count and conflicts_summary use direct SQL queries.
           These will be replaced by the deterministic rule engine in M2.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import DecisionStatusEnum


class WorkloadSummary(BaseModel):
    avg_hours_this_week: float = Field(description="Average faculty hours this week")
    max_hours_this_week: float = Field(description="Maximum hours assigned to any faculty this week")
    min_hours_this_week: float = Field(description="Minimum hours assigned to any faculty this week")
    overloaded_count: int = Field(description="Faculty exceeding their weekly_max_hours")


class ConflictSummary(BaseModel):
    rule_id: str = Field(description="Hard constraint ID (HC-01 to HC-10)")
    description: str
    count: int
    note: str = Field(description="M1 note about accuracy of this count")


class RecentDecision(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    scenario_summary: str
    decision_status: DecisionStatusEnum
    created_at: datetime
    created_by_email: str


class DashboardResponse(BaseModel):
    """
    Operational dashboard data.
    All metrics are derived from real database content — no hardcoded values.
    ⚠ DATA LABEL: All underlying data is SYNTHETIC.
    """
    # ── Counts ────────────────────────────────────────────────────────────
    total_faculty: int
    total_courses: int
    total_sections: int
    total_rooms: int
    total_timetable_entries: int

    # ── Today (DEMO_TODAY) ───────────────────────────────────────────────
    demo_today: date
    faculty_on_leave_today: int
    faculty_available_today: int
    occurrences_today: int

    # ── This week (Mon–Sun containing DEMO_TODAY) ─────────────────────────
    occurrences_this_week: int

    # ── Conflicts (M1 approximation — rule engine replaces in M2) ─────────
    conflict_count: int
    conflicts_summary: list[ConflictSummary]

    # ── Workload ──────────────────────────────────────────────────────────
    workload_summary: WorkloadSummary

    # ── Recent decisions ─────────────────────────────────────────────────
    recent_decisions: list[RecentDecision]

    # ── Metadata ─────────────────────────────────────────────────────────
    data_label: str = "SYNTHETIC — NOT REAL INSTITUTIONAL DATA"
