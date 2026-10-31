"""
Dashboard API route.

GET /dashboard — returns operational statistics from the database.

All metrics are computed from real database content.
No hardcoded values. No mocked results.

Access: HOD or Principal (enforced on backend).
HOD receives institution-wide stats in M1; department-filtered stats added in M5.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import CurrentUser, require_hod_or_principal
from app.db.models import User
from app.db.session import get_db
from app.schemas.dashboard import (
    ConflictSummary,
    DashboardResponse,
    RecentDecision,
    WorkloadSummary,
)
from app.services.timetable import (
    get_conflict_counts,
    get_faculty_on_leave_on,
    get_occurrences_count_for_week,
    get_timetable_stats,
    get_workload_this_week,
    week_bounds,
)
from sqlalchemy import text

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "",
    response_model=DashboardResponse,
    summary="Operational dashboard statistics",
    description=(
        "Returns live statistics derived from the database. "
        "All data is SYNTHETIC for the prototype. "
        "Conflict counts in M1 use direct SQL approximations; "
        "the rule engine (M2) will replace these with structured violations."
    ),
)
def get_dashboard(
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> DashboardResponse:
    today = settings.today
    week_monday, week_sunday = week_bounds(today)

    # ── Core counts ───────────────────────────────────────────────────────
    stats = get_timetable_stats(db)

    # ── Today ─────────────────────────────────────────────────────────────
    on_leave_today = get_faculty_on_leave_on(db, today)
    faculty_available = stats["total_faculty"] - on_leave_today

    occurrences_today = db.execute(
        text("""
            SELECT COUNT(*) FROM class_occurrence
            WHERE occurrence_date = :d AND status != 'cancelled'
        """),
        {"d": today},
    ).scalar() or 0

    # ── This week ─────────────────────────────────────────────────────────
    occurrences_week = get_occurrences_count_for_week(db, week_monday)

    # ── Conflicts (M1 SQL approximation) ─────────────────────────────────
    raw_conflicts = get_conflict_counts(db)
    conflicts = [ConflictSummary(**c) for c in raw_conflicts]
    total_conflicts = sum(c.count for c in conflicts)

    # ── Workload ──────────────────────────────────────────────────────────
    wl_raw = get_workload_this_week(db, week_monday, week_sunday)
    workload = WorkloadSummary(**wl_raw)

    # ── Recent decisions ─────────────────────────────────────────────────
    decision_rows = db.execute(
        text("""
            SELECT
                d.id,
                d.scenario,
                d.decision_status,
                d.created_at,
                u.email AS created_by_email
            FROM decision d
            JOIN "user" u ON d.created_by_id = u.id
            ORDER BY d.created_at DESC
            LIMIT 5
        """)
    ).fetchall()

    recent: list[RecentDecision] = []
    for row in decision_rows:
        scenario = row.scenario or {}
        summary = scenario.get("summary", f"Decision {str(row.id)[:8]}")
        recent.append(
            RecentDecision(
                id=row.id,
                scenario_summary=summary,
                decision_status=row.decision_status,
                created_at=row.created_at,
                created_by_email=row.created_by_email,
            )
        )

    return DashboardResponse(
        total_faculty=stats["total_faculty"],
        total_courses=stats["total_courses"],
        total_sections=stats["total_sections"],
        total_rooms=stats["total_rooms"],
        total_timetable_entries=stats["total_entries"],
        demo_today=today,
        faculty_on_leave_today=on_leave_today,
        faculty_available_today=faculty_available,
        occurrences_today=occurrences_today,
        occurrences_this_week=occurrences_week,
        conflict_count=total_conflicts,
        conflicts_summary=conflicts,
        workload_summary=workload,
        recent_decisions=recent,
    )
