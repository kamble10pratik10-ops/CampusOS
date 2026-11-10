"""
Academic infrastructure API routes (Milestone M5).

Endpoints:
- GET /faculty: List faculty members with department details and workload capacity
- GET /departments: List academic departments
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import check_department_access, require_hod_or_principal
from app.db.models import Department, Faculty, RoleEnum, User
from app.db.session import get_db

router = APIRouter(tags=["academic"])


class DepartmentPublic(BaseModel):
    id: uuid.UUID
    code: str
    name: str

    model_config = {"from_attributes": True}


class FacultyPublic(BaseModel):
    id: uuid.UUID
    name: str
    employee_code: str
    department_id: uuid.UUID
    department_name: str
    department_code: str
    weekly_max_hours: float
    is_active: bool

    model_config = {"from_attributes": True}


@router.get(
    "/departments",
    response_model=list[DepartmentPublic],
    summary="List all departments",
)
def list_departments(
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DepartmentPublic]:
    depts = db.query(Department).order_by(Department.code).all()
    return [DepartmentPublic.model_validate(d) for d in depts]


@router.get(
    "/faculty",
    response_model=list[FacultyPublic],
    summary="List faculty members",
)
def list_faculty(
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
    department_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[FacultyPublic]:
    query = (
        db.query(Faculty)
        .options(joinedload(Faculty.department))
        .filter(Faculty.is_active.is_(True))
    )

    if current_user.role == RoleEnum.hod:
        if department_id is not None:
            check_department_access(current_user, department_id)
        else:
            department_id = current_user.department_id

    if department_id is not None:
        query = query.filter(Faculty.department_id == department_id)

    faculty_list = query.order_by(Faculty.name).all()

    return [
        FacultyPublic(
            id=f.id,
            name=f.name,
            employee_code=f.employee_code,
            department_id=f.department_id,
            department_name=f.department.name if f.department else "",
            department_code=f.department.code if f.department else "",
            weekly_max_hours=f.weekly_max_hours,
            is_active=f.is_active,
        )
        for f in faculty_list
    ]

