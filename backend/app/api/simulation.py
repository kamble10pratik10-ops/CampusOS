"""
Simulation and Audit API route (Milestone M4).

Endpoints:
- POST /simulation/run: Executes non-mutating what-if simulation pipeline, runs Critic, persists audit.
- GET /simulation/history: Retrieves audit history of past simulations and decisions.
- GET /simulation/{decision_id}: Retrieves specific audit record by ID.
- POST /simulation/{decision_id}/approve: Approves a simulated decision in audit log.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import check_department_access, require_hod_or_principal
from app.db.models import Decision, DecisionStatusEnum, RoleEnum, User
from app.db.session import get_db
from app.engine.simulation import SimulationPipeline
from app.schemas.simulation import (
    AuditListItem,
    SimulationRequest,
    SimulationResponse,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post(
    "/run",
    response_model=SimulationResponse,
    summary="Run non-mutating What-If simulation",
    description=(
        "Executes the full 12-step What-If simulation pipeline. Solves joint replacement, "
        "runs independent Critic validation, verifies HC-10 non-mutation, and records an "
        "immutable audit record in the decision table.\n\n"
        "⚠ All underlying data is SYNTHETIC."
    ),
)
def run_simulation(
    request: SimulationRequest,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> SimulationResponse:
    pipeline = SimulationPipeline(db)
    response = pipeline.run_simulation(request, current_user)
    return response


@router.get(
    "/history",
    response_model=list[AuditListItem],
    summary="List simulation and decision audit records",
    description="Returns recent decision and simulation audit records from the immutable audit log.",
)
def get_simulation_history(
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[AuditListItem]:
    query = db.query(Decision).options(joinedload(Decision.created_by_user))
    if current_user.role == RoleEnum.hod:
        query = query.join(Decision.created_by_user).filter(
            (User.department_id == current_user.department_id)
            | (Decision.scenario["department_id"].astext == str(current_user.department_id))
        )

    rows = (
        query
        .order_by(Decision.created_at.desc())
        .limit(limit)
        .all()
    )

    items: list[AuditListItem] = []
    for r in rows:
        scenario = r.scenario or {}
        items.append(
            AuditListItem(
                id=r.id,
                scenario_summary=scenario.get("scenario_name", f"Decision {str(r.id)[:8]}"),
                decision_status=r.decision_status,
                critic_status=scenario.get("critic_status", "unknown"),
                coverage_percentage=scenario.get("coverage_percentage", 0.0),
                total_affected=scenario.get("total_affected", 0),
                created_at=r.created_at,
                created_by_email=r.created_by_user.email if r.created_by_user else "unknown",
                runtime_ms=r.runtime_ms,
            )
        )
    return items


@router.get(
    "/{decision_id}",
    summary="Get detailed audit record by ID",
    description="Retrieves a specific decision record and its associated evidence trail.",
)
def get_decision_detail(
    decision_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    decision = (
        db.query(Decision)
        .options(
            joinedload(Decision.created_by_user),
            joinedload(Decision.evidence),
        )
        .filter(Decision.id == decision_id)
        .first()
    )

    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision audit record {decision_id} not found.",
        )

    if current_user.role == RoleEnum.hod:
        dept_id = (decision.scenario or {}).get("department_id")
        created_by_dept = decision.created_by_user.department_id if decision.created_by_user else None
        if dept_id and dept_id != str(current_user.department_id):
            check_department_access(current_user, uuid.UUID(dept_id))
        elif created_by_dept and created_by_dept != current_user.department_id:
            check_department_access(current_user, created_by_dept)

    evidence_items = [
        {
            "id": str(e.id),
            "ref_type": e.ref_type,
            "ref_id": str(e.ref_id) if e.ref_id else None,
            "description": e.description,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in decision.evidence
    ]

    return {
        "id": str(decision.id),
        "scenario": decision.scenario,
        "created_by_email": decision.created_by_user.email if decision.created_by_user else "unknown",
        "decision_status": decision.decision_status.value,
        "solver_status": decision.solver_status,
        "llm_status": decision.llm_status,
        "runtime_ms": decision.runtime_ms,
        "created_at": decision.created_at.isoformat() if decision.created_at else None,
        "evidence": evidence_items,
    }


@router.post(
    "/{decision_id}/approve",
    summary="Approve a simulation decision in audit trail",
    description=(
        "Updates decision status to 'approved'. Enforces non-mutation: "
        "does not automatically alter operational timetable data."
    ),
)
def approve_decision(
    decision_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    decision = (
        db.query(Decision)
        .options(joinedload(Decision.created_by_user))
        .filter(Decision.id == decision_id)
        .first()
    )
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision {decision_id} not found.",
        )

    if current_user.role == RoleEnum.hod:
        dept_id = (decision.scenario or {}).get("department_id")
        created_by_dept = decision.created_by_user.department_id if decision.created_by_user else None
        if dept_id and dept_id != str(current_user.department_id):
            check_department_access(current_user, uuid.UUID(dept_id))
        elif created_by_dept and created_by_dept != current_user.department_id:
            check_department_access(current_user, created_by_dept)

    decision.decision_status = DecisionStatusEnum.approved
    db.commit()
    db.commit()

    return {
        "decision_id": str(decision.id),
        "decision_status": DecisionStatusEnum.approved.value,
        "message": "Decision successfully marked as approved in audit log. Operational tables remain unmutated.",
    }

