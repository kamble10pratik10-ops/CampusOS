"""
Decisions and What-If API routes (SPEC Section 13 contract compliance).

Provides direct aliases to simulation and decision audit endpoints:
- POST /whatif: Runs What-If simulation pipeline
- GET  /decisions: Lists historical decision audit records
- GET  /decisions/{decision_id}: Retrieves specific decision details and evidence
- POST /decisions/{decision_id}/approve: Approves a simulated decision in audit log
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.simulation import (
    approve_decision as sim_approve,
    get_decision_detail as sim_get_detail,
    get_simulation_history as sim_get_history,
    run_simulation as sim_run,
)
from app.core.permissions import require_hod_or_principal
from app.db.models import User
from app.db.session import get_db
from app.schemas.simulation import (
    AuditListItem,
    SimulationRequest,
    SimulationResponse,
)

router = APIRouter(tags=["decisions"])


@router.post(
    "/whatif",
    response_model=SimulationResponse,
    summary="Run non-mutating What-If simulation (SPEC Section 13 endpoint)",
)
def post_whatif(
    request: SimulationRequest,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> SimulationResponse:
    return sim_run(request=request, current_user=current_user, db=db)


@router.get(
    "/decisions",
    response_model=list[AuditListItem],
    summary="List decision audit records (SPEC Section 13 endpoint)",
)
def list_decisions(
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[AuditListItem]:
    return sim_get_history(current_user=current_user, db=db, limit=limit)


@router.get(
    "/decisions/{decision_id}",
    summary="Get decision detail and evidence by ID (SPEC Section 13 endpoint)",
)
def get_decision(
    decision_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return sim_get_detail(decision_id=decision_id, current_user=current_user, db=db)


@router.post(
    "/decisions/{decision_id}/approve",
    summary="Approve a decision in audit trail (SPEC Section 13 endpoint)",
)
def approve_decision_alias(
    decision_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_hod_or_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return sim_approve(decision_id=decision_id, current_user=current_user, db=db)

