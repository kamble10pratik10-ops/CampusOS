"""
Workload API route (Milestone M2).

GET /workload — calculates faculty workload and capacity utilization across
a target calendar week (Monday to Sunday) using real database records.

Supports:
- Evaluation of weekly hours assigned vs configured weekly_max_hours (HC-07)
- Faculty overload detection
- Optional department filtering
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.permissions import check_department_access, require_hod_or_principal
from app.db.models import ClassOccurrence, Faculty, Period, RoleEnum, TimetableEntry, User
from app.db.session import get_db
from app.engine.rules import get_calendar_week_bounds
from app.schemas.rules import FacultyWorkloadDetail, WorkloadResponse

router = APIRouter(prefix="/workload", tags=["workload"])


@router.get(
    "",
    response_model=WorkloadResponse,
    summary="Faculty workload and capacity utilization",
    description=(
        "Returns workload statistics and per-faculty capacity utilization "
        "for the specified calendar week. Evaluates HC-07 workload caps.\n\n"
        "⚠ All underlying data is SYNTHETIC."
    ),
)
def get_workload(
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
    week_date: Annotated[
        date | None,
        Query(
            description="Any date within the target week. Defaults to DEMO_TODAY.",
        ),
    ] = None,
    department_id: Annotated[
        uuid.UUID | None,
        Query(
            description="Filter faculty to this department ID.",
        ),
    ] = None,
) -> WorkloadResponse:
    if current_user.role == RoleEnum.hod and department_id is not None:
        check_department_access(current_user, department_id)

    target = week_date or settings.today
    week_start, week_end = get_calendar_week_bounds(target)

    # 1. Fetch faculty
    fac_query = db.query(Faculty).options(joinedload(Faculty.department)).filter(Faculty.is_active.is_(True))
    if department_id is not None:
        fac_query = fac_query.filter(Faculty.department_id == department_id)
    faculty_list = fac_query.all()

    # 2. Fetch class occurrences in the week
    occs = (
        db.query(ClassOccurrence)
        .options(
            joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.period),
        )
        .filter(
            ClassOccurrence.occurrence_date >= week_start,
            ClassOccurrence.occurrence_date <= week_end,
            ClassOccurrence.status != "cancelled",
        )
        .all()
    )

    # Map hours and count by faculty_id
    hours_by_fac: dict[uuid.UUID, float] = {f.id: 0.0 for f in faculty_list}
    count_by_fac: dict[uuid.UUID, int] = {f.id: 0 for f in faculty_list}

    for occ in occs:
        fid = occ.effective_faculty_id
        if not fid or fid not in hours_by_fac:
            continue

        # Get duration
        duration = 1.0
        if occ.timetable_entry and occ.timetable_entry.period:
            duration = occ.timetable_entry.period.duration_hours

        hours_by_fac[fid] += duration
        count_by_fac[fid] += 1

    details: list[FacultyWorkloadDetail] = []
    overloaded_count = 0

    for f in faculty_list:
        assigned_h = round(hours_by_fac[f.id], 2)
        count = count_by_fac[f.id]
        max_h = f.weekly_max_hours
        util_rate = round(assigned_h / max(max_h, 1.0), 3)
        is_over = assigned_h > max_h
        if is_over:
            overloaded_count += 1

        dept_code = f.department.code if f.department else "N/A"
        details.append(
            FacultyWorkloadDetail(
                faculty_id=f.id,
                faculty_name=f.name,
                employee_code=f.employee_code,
                department_code=dept_code,
                weekly_max_hours=max_h,
                assigned_hours=assigned_h,
                assigned_occurrences_count=count,
                utilization_rate=util_rate,
                is_overloaded=is_over,
            )
        )

    all_hours = [d.assigned_hours for d in details]
    total_fac = len(details)
    avg_h = round(sum(all_hours) / max(total_fac, 1), 2)
    max_h = max(all_hours) if all_hours else 0.0
    min_h = min(all_hours) if all_hours else 0.0

    return WorkloadResponse(
        week_start=week_start,
        week_end=week_end,
        total_faculty=total_fac,
        overloaded_count=overloaded_count,
        avg_hours=avg_h,
        max_hours=max_h,
        min_hours=min_h,
        faculty_workloads=details,
    )
