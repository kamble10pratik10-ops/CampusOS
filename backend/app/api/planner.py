"""
Optimization Planner API route (Milestone M3).

POST /planner/optimize — runs candidate eligibility analysis and joint optimization
using Google OR-Tools CP-SAT and Greedy Baseline.

GET /planner/eligibility/{occurrence_id} — returns candidate eligibility and
structured rejection reasons for an individual class occurrence.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.permissions import check_department_access, require_hod_or_principal
from app.db.models import ClassOccurrence, Faculty, RoleEnum, TimetableEntry, User
from app.db.session import get_db
from app.engine.eligibility import CandidateGenerator
from app.engine.planner import JointOptimizationPlanner
from app.schemas.planner import (
    OccurrenceEligibility,
    OptimizationRequest,
    PlannerResponse,
)

router = APIRouter(prefix="/planner", tags=["planner"])


@router.post(
    "/optimize",
    response_model=PlannerResponse,
    summary="Joint optimization replacement planning",
    description=(
        "Jointly solves faculty replacements for affected class occurrences using "
        "Google OR-Tools CP-SAT. Generates up to 3 distinct feasible plans plus a greedy "
        "baseline. Validates all plans independently with the deterministic RuleEngine.\n\n"
        "⚠ All underlying data is SYNTHETIC."
    ),
)
def run_optimization(
    request: OptimizationRequest,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> PlannerResponse:
    if current_user.role == RoleEnum.hod and request.faculty_id:
        target_fac = db.get(Faculty, request.faculty_id)
        if target_fac and target_fac.department_id != current_user.department_id:
            check_department_access(current_user, target_fac.department_id)

    planner = JointOptimizationPlanner(db)

    # 1. Resolve affected occurrences
    occurrences = planner.resolve_affected_occurrences(
        occurrence_ids=request.occurrence_ids,
        faculty_id=request.faculty_id,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    if not occurrences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No class occurrences found matching the provided criteria.",
        )

    if current_user.role == RoleEnum.hod:
        for occ in occurrences:
            if (
                occ.timetable_entry
                and occ.timetable_entry.course
                and occ.timetable_entry.course.department_id != current_user.department_id
            ):
                check_department_access(current_user, occ.timetable_entry.course.department_id)

    # 2. Execute joint optimization
    response = planner.plan(
        occurrences,
        max_alternatives=request.max_alternatives,
        weights=request.weights,
    )

    return response


@router.get(
    "/eligibility/{occurrence_id}",
    response_model=OccurrenceEligibility,
    summary="Inspect candidate eligibility and rejection reasons",
    description=(
        "Returns the complete evaluation of the faculty candidate pool for a specific "
        "class occurrence, including structured rejection reasons for ineligible candidates "
        "and soft preference scores for eligible candidates."
    ),
)
def get_occurrence_eligibility(
    occurrence_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> OccurrenceEligibility:
    occ = (
        db.query(ClassOccurrence)
        .options(
            joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.period),
            joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.course),
            joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.section),
            joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.room),
        )
        .filter(ClassOccurrence.id == occurrence_id)
        .first()
    )

    if not occ:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class occurrence {occurrence_id} not found.",
        )

    if current_user.role == RoleEnum.hod:
        if (
            occ.timetable_entry
            and occ.timetable_entry.course
            and occ.timetable_entry.course.department_id != current_user.department_id
        ):
            check_department_access(current_user, occ.timetable_entry.course.department_id)

    generator = CandidateGenerator(db)
    return generator.get_occurrence_eligibility(occ)

