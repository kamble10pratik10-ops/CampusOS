"""
Conflicts API route (Milestone M2).

GET /conflicts — evaluates timetable against all hard constraints and soft preferences
using the authoritative deterministic RuleEngine.

Supports:
- Evaluation of weekly recurring template (default)
- Evaluation of dated occurrences (when date query param is provided)
- Optional department filtering
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import check_department_access, require_hod_or_principal
from app.db.models import ClassOccurrence, Course, RoleEnum, TimetableEntry, User
from app.db.session import get_db
from app.engine.rules import RuleEngine
from app.schemas.rules import ConflictsResponse

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get(
    "",
    response_model=ConflictsResponse,
    summary="Detect timetable conflicts and constraint violations",
    description=(
        "Evaluates the timetable against deterministic hard constraints (HC-01 through HC-08). "
        "Returns typed structured violations with rule IDs, affected entity IDs, "
        "traceable evidence refs, and deterministic signatures.\n\n"
        "⚠ All underlying data is SYNTHETIC."
    ),
)
def get_conflicts(
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
    target_date: Annotated[
        date | None,
        Query(
            alias="date",
            description="Evaluate dated class occurrences on this specific date. If omitted, evaluates weekly template.",
        ),
    ] = None,
    department_id: Annotated[
        uuid.UUID | None,
        Query(
            description="Filter evaluated classes/entries to this department ID.",
        ),
    ] = None,
    scope: Annotated[
        str,
        Query(
            description="Scope of evaluation: 'template' (weekly template) or 'dated' (dated occurrences).",
        ),
    ] = "template",
) -> ConflictsResponse:
    if current_user.role == RoleEnum.hod and department_id is not None:
        check_department_access(current_user, department_id)

    engine = RuleEngine(db)

    if target_date is not None or scope == "dated":
        eval_date = target_date or settings.today
        query = db.query(ClassOccurrence).filter(
            ClassOccurrence.occurrence_date == eval_date,
            ClassOccurrence.status != "cancelled",
        )
        if department_id is not None:
            query = query.join(ClassOccurrence.timetable_entry).join(TimetableEntry.course).filter(
                Course.department_id == department_id
            )
        occurrences = query.all()
        result = engine.validate_dated_occurrences(occurrences=occurrences, target_date=eval_date)
        eval_scope = "dated_occurrences"
        res_date = eval_date
    else:
        query = db.query(TimetableEntry)
        if department_id is not None:
            query = query.join(TimetableEntry.course).filter(Course.department_id == department_id)
        entries = query.all()
        result = engine.validate_timetable_template(entries=entries)
        eval_scope = "template"
        res_date = None

    return ConflictsResponse(
        is_valid=result.is_valid,
        total_conflicts=result.total_violations,
        hard_conflicts=result.hard_violations_count,
        soft_conflicts=result.soft_violations_count,
        violations=result.violations,
        by_rule=result.by_rule,
        evaluation_scope=eval_scope,
        target_date=res_date,
    )

