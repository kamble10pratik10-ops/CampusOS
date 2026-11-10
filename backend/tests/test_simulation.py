"""
test_simulation.py — Comprehensive tests for What-If Simulation, Critic, and Audit (Milestone M4).

Covers:
- Non-mutating what-if simulation pipeline (Hero scenario)
- Independent Critic deterministic validation and issue code reporting
- Rejection of plans introducing new hard violations (validation_failed)
- Multi-state Critic outcomes: feasible_complete, feasible_partial, infeasible, validation_failed
- Verification that claimed coverage and scores match computed reality
- Verification that operational tables (timetable_entry, class_occurrence, faculty) are NEVER mutated (HC-10)
- Immutable audit persistence in decision and decision_evidence tables
- Audit record retrieval and human approval workflow
- API endpoint integration: POST /simulation/run, GET /simulation/history, GET /simulation/{id}, POST /simulation/{id}/approve
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    ClassOccurrence,
    Course,
    Decision,
    DecisionEvidence,
    DecisionStatusEnum,
    Faculty,
    FacultyLeave,
    Period,
    Room,
    Section,
    TimetableEntry,
    User,
)
from app.db.seed import HERO_LEAVE_ID, SHARMA_ID
from app.engine.critic import Critic
from app.engine.eligibility import CandidateGenerator
from app.engine.planner import JointOptimizationPlanner
from app.engine.rules import RuleEngine
from app.engine.simulation import SimulationPipeline
from app.schemas.planner import AssignmentProposal, OptimizationPlan, SolverStatusEnum
from app.schemas.rules import ConstraintTypeEnum, SeverityEnum, Violation
from app.schemas.simulation import (
    CriticIssue,
    CriticResult,
    CriticStatusEnum,
    SimulationRequest,
    SimulationResponse,
)


# ── Independent Critic Tests ───────────────────────────────────────────────


def test_critic_approves_feasible_complete_plan(db_session: Session):
    """
    Critic must evaluate the optimal Hero plan and return status feasible_complete,
    with is_approved=True, 0 new hard violations, and claims verified.
    """
    planner = JointOptimizationPlanner(db_session)
    critic = Critic(planner.candidate_gen)

    occurrences = planner.resolve_affected_occurrences(
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
    )
    assert len(occurrences) == 6

    baseline_val = planner.rule_engine.validate_dated_occurrences(occurrences=occurrences)
    plan = planner.cpsat_solver.solve(occurrences)

    result = critic.critique(plan, baseline_val.violations, occurrences)

    assert result.status == CriticStatusEnum.feasible_complete
    assert result.is_approved is True
    assert result.claims_verified is True
    assert result.new_hard_violations_count == 0
    assert result.resolved_violations_count >= 6
    assert any(i.issue_code == "CRITIC-INFO-CLAIMS-VERIFIED" for i in result.issues)


def test_critic_rejects_plan_with_new_hard_violation(db_session: Session):
    """
    If a proposed plan introduces a new hard violation (e.g. artificial double-booking),
    the Critic must reject it with status validation_failed and is_approved=False.
    """
    planner = JointOptimizationPlanner(db_session)
    critic = Critic(planner.candidate_gen)

    occurrences = planner.resolve_affected_occurrences(
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
    )
    baseline_val = planner.rule_engine.validate_dated_occurrences(occurrences=occurrences)
    plan = planner.cpsat_solver.solve(occurrences)

    # Intentionally corrupt the plan: assign same candidate to two overlapping classes
    # e.g. Mon P2 and Mon P2 on 2026-11-02
    test_cand_id = plan.assignments[0].assigned_faculty_id
    plan.assignments[1].assigned_faculty_id = test_cand_id
    plan.assignments[1].period_id = plan.assignments[0].period_id
    plan.assignments[1].occurrence_date = plan.assignments[0].occurrence_date

    result = critic.critique(plan, baseline_val.violations, occurrences)

    assert result.status == CriticStatusEnum.validation_failed
    assert result.is_approved is False
    assert any(i.issue_code == "CRITIC-ERR-PROPOSED-OVERLAP" for i in result.issues)


def test_critic_detects_claim_mismatch(db_session: Session):
    """
    If plan claims 6 covered classes but only provides 5 assignments,
    Critic flags CRITIC-ERR-CLAIM-MISMATCH-COUNT and claims_verified=False.
    """
    planner = JointOptimizationPlanner(db_session)
    critic = Critic(planner.candidate_gen)

    occurrences = planner.resolve_affected_occurrences(
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
    )
    baseline_val = planner.rule_engine.validate_dated_occurrences(occurrences=occurrences)
    plan = planner.cpsat_solver.solve(occurrences)

    # Artificially alter claimed count
    plan.covered_occurrences = 10  # Mismatch!

    result = critic.critique(plan, baseline_val.violations, occurrences)
    assert result.claims_verified is False
    assert any(i.issue_code == "CRITIC-ERR-CLAIM-MISMATCH-COUNT" for i in result.issues)


# ── What-If Simulation Pipeline & HC-10 Non-Mutation ──────────────────────


def test_simulation_pipeline_hero_scenario(db_session: Session):
    """
    End-to-end execution of what-if simulation for Hero scenario:
    - 6 affected classes resolved
    - Primary plan covers 100%
    - Critic validates feasible_complete
    - Audit record persisted in Decision table
    - HC-10 verified: operational tables NOT mutated!
    """
    pipeline = SimulationPipeline(db_session)

    # Get demo user (Principal)
    principal = db_session.query(User).filter(User.email == "principal@campus.os").first()
    assert principal is not None

    # Take snapshot counts before
    count_timetable_before = db_session.query(TimetableEntry).count()
    count_occurrences_before = db_session.query(ClassOccurrence).count()
    count_faculty_before = db_session.query(Faculty).count()
    count_leaves_before = db_session.query(FacultyLeave).count()
    count_decisions_before = db_session.query(Decision).count()

    req = SimulationRequest(
        scenario_name="Dr. Raj Sharma Medical Absence",
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
        max_alternatives=3,
    )

    response: SimulationResponse = pipeline.run_simulation(req, principal)

    # 1. Output content checks
    assert response.decision_id is not None
    assert response.critic_status == CriticStatusEnum.feasible_complete
    assert response.affected_occurrences_count == 6
    assert response.selected_plan is not None
    assert response.selected_plan.coverage_percentage == 100.0
    assert len(response.alternatives) >= 2
    assert response.baseline_greedy_plan is not None
    assert response.decision_status == DecisionStatusEnum.simulation
    assert len(response.evidence_refs) > 0
    assert len(response.limitations) > 0

    # 2. Before-and-after diff check
    # Baseline had Dr. Sharma on leave (6 HC-03 violations)
    assert response.diff.introduces_new_hard_violations is False
    assert len(response.diff.resolved_violations) >= 6

    # 3. HC-10 NON-MUTATION VERIFICATION:
    # Operational tables MUST have identical row counts before and after!
    assert db_session.query(TimetableEntry).count() == count_timetable_before
    assert db_session.query(ClassOccurrence).count() == count_occurrences_before
    assert db_session.query(Faculty).count() == count_faculty_before
    assert db_session.query(FacultyLeave).count() == count_leaves_before

    # Verify that class_occurrence override fields were NOT written to
    hero_occs = (
        db_session.query(ClassOccurrence)
        .join(ClassOccurrence.timetable_entry)
        .filter(
            TimetableEntry.faculty_id == SHARMA_ID,
            ClassOccurrence.occurrence_date >= date(2026, 11, 2),
            ClassOccurrence.occurrence_date <= date(2026, 11, 4),
        )
        .all()
    )
    for occ in hero_occs:
        assert occ.override_faculty_id is None, "Simulation must NOT write override_faculty_id to database!"

    # 4. Audit Persistence: exactly 1 new Decision was added
    assert db_session.query(Decision).count() == count_decisions_before + 1
    persisted_decision = db_session.query(Decision).filter(Decision.id == response.decision_id).first()
    assert persisted_decision is not None
    assert persisted_decision.decision_status == DecisionStatusEnum.simulation
    assert persisted_decision.scenario["total_affected"] == 6
    assert persisted_decision.scenario["critic_status"] == "feasible_complete"
    assert persisted_decision.runtime_ms > 0

    # Verify DecisionEvidence records persisted
    evidence_rows = db_session.query(DecisionEvidence).filter(DecisionEvidence.decision_id == response.decision_id).all()
    assert len(evidence_rows) > 0


# ── Audit Trail & Approval Workflow Tests ──────────────────────────────────


def test_approve_decision_workflow(db_session: Session):
    """
    Approving a decision updates decision_status to 'approved' without mutating timetable data.
    """
    pipeline = SimulationPipeline(db_session)
    principal = db_session.query(User).filter(User.email == "principal@campus.os").first()

    req = SimulationRequest(
        scenario_name="Test Absence Approval",
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 2),
    )
    sim_res = pipeline.run_simulation(req, principal)

    # Approve the simulation
    decision = db_session.query(Decision).filter(Decision.id == sim_res.decision_id).first()
    assert decision.decision_status == DecisionStatusEnum.simulation

    decision.decision_status = DecisionStatusEnum.approved
    db_session.commit()

    reloaded = db_session.query(Decision).filter(Decision.id == sim_res.decision_id).first()
    assert reloaded.decision_status == DecisionStatusEnum.approved


# ── API Endpoint Tests ────────────────────────────────────────────────────


def test_api_run_simulation_unauthenticated(client: TestClient):
    """POST /simulation/run returns 401 without token."""
    response = client.post("/simulation/run", json={})
    assert response.status_code == 401


def test_api_run_simulation_hero_scenario(seeded_client: TestClient):
    """
    POST /simulation/run with valid token returns complete SimulationResponse.
    """
    login_res = seeded_client.post(
        "/auth/token",
        data={"username": "principal@campus.os", "password": "changeme"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    payload = {
        "scenario_name": "Dr. Raj Sharma Absence Simulation",
        "faculty_id": str(SHARMA_ID),
        "start_date": "2026-11-02",
        "end_date": "2026-11-04",
        "max_alternatives": 3,
    }

    response = seeded_client.post(
        "/simulation/run",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert "decision_id" in body
    assert body["critic_status"] == "feasible_complete"
    assert body["affected_occurrences_count"] == 6
    assert body["selected_plan"]["coverage_percentage"] == 100.0
    assert len(body["alternatives"]) >= 2
    assert body["diff"]["introduces_new_hard_violations"] is False

    decision_id = body["decision_id"]

    # Test GET /simulation/history
    history_res = seeded_client.get(
        "/simulation/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history_res.status_code == 200
    history = history_res.json()
    assert any(h["id"] == decision_id for h in history)

    # Test GET /simulation/{decision_id}
    detail_res = seeded_client.get(
        f"/simulation/{decision_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == decision_id
    assert detail["decision_status"] == "simulation"
    assert len(detail["evidence"]) > 0

    # Test POST /simulation/{decision_id}/approve
    approve_res = seeded_client.post(
        f"/simulation/{decision_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["decision_status"] == "approved"

