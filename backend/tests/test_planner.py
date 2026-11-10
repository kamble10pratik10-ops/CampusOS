"""
test_planner.py — Comprehensive tests for Candidate Generation and Optimization (Milestone M3).

Covers:
- Candidate eligibility filters and structured rejection reasons (HC-01, HC-03, HC-06, HC-07, HC-08)
- Soft preference scoring on eligible candidates (SP-01 to SP-04)
- CP-SAT joint optimization solver on Hero scenario (Dr. Raj Sharma leave)
- Distinct multi-alternative plan generation
- Partial and infeasible scenario handling with explicit uncovered assignment explanations
- Greedy baseline solver and comparison against CP-SAT
- Independent validation with RuleEngine (zero new hard violations)
- API endpoint integration: POST /planner/optimize, GET /planner/eligibility/{occurrence_id}
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    ClassOccurrence,
    Course,
    Faculty,
    FacultyExpertise,
    FacultyLeave,
    Period,
    Room,
    Section,
    TimetableEntry,
)
from app.db.seed import HERO_LEAVE_ID, SHARMA_ID
from app.engine.eligibility import CandidateGenerator
from app.engine.planner import JointOptimizationPlanner
from app.engine.rules import RuleEngine
from app.engine.solver import CPSATSolver, GreedyBaselineSolver
from app.schemas.planner import (
    CandidateEligibility,
    FeasibilityStatusEnum,
    OptimizationPlan,
    OptimizationRequest,
    PlannerResponse,
    SolverStatusEnum,
)


# ── Candidate Eligibility & Rejections ─────────────────────────────────────


def test_candidate_eligibility_hero_scenario(db_session: Session):
    """
    CandidateGenerator evaluates all active faculty for an affected occurrence.
    For Dr. Sharma's class on 2026-11-02, it must:
    - Exclude Dr. Sharma (original faculty)
    - Identify eligible candidates with calculated soft scores
    - Identify ineligible candidates with structured rejection reasons
    """
    generator = CandidateGenerator(db_session)

    # Find one of Dr. Sharma's affected occurrences on 2026-11-02
    occ = (
        db_session.query(ClassOccurrence)
        .join(ClassOccurrence.timetable_entry)
        .filter(
            TimetableEntry.faculty_id == SHARMA_ID,
            ClassOccurrence.occurrence_date == date(2026, 11, 2),
        )
        .first()
    )
    assert occ is not None

    eligibility = generator.get_occurrence_eligibility(occ)

    assert eligibility.total_candidates_evaluated >= 29
    assert eligibility.eligible_count > 0
    assert len(eligibility.eligible_candidates) == eligibility.eligible_count
    assert len(eligibility.ineligible_candidates) > 0

    # Verify that eligible candidates have soft scores populated
    top_cand = eligibility.eligible_candidates[0]
    assert top_cand.is_eligible is True
    assert len(top_cand.rejection_reasons) == 0
    assert top_cand.total_soft_score > 0.0
    assert "SP-01" in top_cand.soft_scores
    assert "SP-02" in top_cand.soft_scores

    # Verify that ineligible candidates have structured rejection reasons
    for inelig in eligibility.ineligible_candidates:
        assert inelig.is_eligible is False
        assert len(inelig.rejection_reasons) > 0
        r = inelig.rejection_reasons[0]
        assert r.rule_id in ("HC-01", "HC-03", "HC-06", "HC-07", "HC-08")
        assert len(r.reason) > 0


def test_candidate_rejection_on_leave(db_session: Session):
    """A faculty member on approved leave on target date must be rejected with HC-03."""
    generator = CandidateGenerator(db_session)

    # Dr. Sharma is on leave 2026-11-02
    sharma_faculty = generator.faculty_map[SHARMA_ID]

    # Pick any occurrence on 2026-11-02
    occ = (
        db_session.query(ClassOccurrence)
        .filter(ClassOccurrence.occurrence_date == date(2026, 11, 2))
        .first()
    )
    assert occ is not None

    cand_eval = generator.evaluate_candidate(sharma_faculty, occ)
    assert cand_eval.is_eligible is False
    assert any(r.rule_id == "HC-03" for r in cand_eval.rejection_reasons)


def test_candidate_rejection_missing_expertise(db_session: Session):
    """A faculty member lacking the course's required expertise tag must be rejected with HC-06."""
    generator = CandidateGenerator(db_session)

    # Find a course that requires 'ai_ml' or another tag
    ml_course = db_session.query(Course).filter(Course.required_expertise_tag.isnot(None)).first()
    assert ml_course is not None

    # Find an occurrence for this course
    occ = (
        db_session.query(ClassOccurrence)
        .join(ClassOccurrence.timetable_entry)
        .filter(TimetableEntry.course_id == ml_course.id)
        .first()
    )
    assert occ is not None

    # Find a faculty member who does not have this expertise tag
    req_tag = ml_course.required_expertise_tag
    non_expert = None
    for f in generator.all_faculty:
        if req_tag not in generator.expertise_map.get(f.id, {}):
            non_expert = f
            break

    assert non_expert is not None
    cand_eval = generator.evaluate_candidate(non_expert, occ)
    assert cand_eval.is_eligible is False
    assert any(r.rule_id == "HC-06" for r in cand_eval.rejection_reasons)


# ── CP-SAT Joint Optimization Solver ──────────────────────────────────────


def test_cpsat_solver_hero_scenario(db_session: Session):
    """
    CP-SAT must jointly solve the 6 affected occurrences for Dr. Raj Sharma.
    Acceptance:
    - 100% coverage (all 6 classes assigned)
    - Optimal solver status
    - Validated by independent RuleEngine with 0 new hard violations
    - Score breakdown populated
    """
    planner = JointOptimizationPlanner(db_session)

    # 1. Resolve affected occurrences for Dr. Sharma during leave
    occurrences = planner.resolve_affected_occurrences(
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
    )
    assert len(occurrences) == 6

    # 2. Run CP-SAT solver
    plan = planner.cpsat_solver.solve(
        occurrences,
        plan_id="hero_plan_a",
        plan_name="Hero Optimal Plan",
    )

    assert plan.solver_status in (SolverStatusEnum.optimal, SolverStatusEnum.feasible)
    assert plan.total_occurrences == 6
    assert plan.covered_occurrences == 6
    assert plan.uncovered_count == 0
    assert plan.coverage_percentage == 100.0
    assert len(plan.assignments) == 6
    assert plan.overall_score > 0.0
    assert plan.solve_time_ms > 0.0

    # 3. Independent validation via RuleEngine
    validated_plan = planner.validate_proposed_plan(plan, occurrences)
    assert validated_plan.is_valid is True
    assert validated_plan.validation_result is not None
    assert "HC-03" not in validated_plan.validation_result.by_rule


def test_cpsat_solver_multi_alternatives(db_session: Session):
    """
    solve_alternatives must generate up to 3 distinct feasible plans.
    """
    planner = JointOptimizationPlanner(db_session)

    occurrences = planner.resolve_affected_occurrences(
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
    )
    assert len(occurrences) == 6

    plans = planner.cpsat_solver.solve_alternatives(occurrences, max_alternatives=3)

    assert len(plans) >= 2
    for p in plans:
        assert p.solver_status in (SolverStatusEnum.optimal, SolverStatusEnum.feasible)
        assert p.covered_occurrences == 6
        assert len(p.assignments) == 6

    # Verify that alternative plans have distinct assignments
    sol_a = {a.occurrence_id: a.assigned_faculty_id for a in plans[0].assignments}
    sol_b = {a.occurrence_id: a.assigned_faculty_id for a in plans[1].assignments}
    assert sol_a != sol_b, "Plan B must be genuinely distinct from Plan A"


# ── Greedy Baseline Solver ────────────────────────────────────────────────


def test_greedy_baseline_solver(db_session: Session):
    """
    Greedy baseline solver processes occurrences chronologically and generates a valid plan.
    """
    planner = JointOptimizationPlanner(db_session)

    occurrences = planner.resolve_affected_occurrences(
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
    )
    assert len(occurrences) == 6

    greedy_plan = planner.greedy_solver.solve(occurrences)

    assert greedy_plan.solver_type == "greedy_baseline"
    assert greedy_plan.total_occurrences == 6
    assert greedy_plan.covered_occurrences >= 5  # greedy covers high percentage
    assert greedy_plan.coverage_percentage > 80.0
    assert greedy_plan.solve_time_ms > 0.0

    # Independent validation
    validated_greedy = planner.validate_proposed_plan(greedy_plan, occurrences)
    assert validated_greedy.is_valid is True


# ── Scenario Feasibility Distinctions ──────────────────────────────────────


def test_planner_feasibility_distinction(db_session: Session):
    """
    Planner must distinguish:
    - Feasible scenario: 100% coverage
    - Partial scenario: < 100% coverage with explicit uncovered explanations
    """
    planner = JointOptimizationPlanner(db_session)

    # 1. Feasible: Hero scenario (all 6 covered)
    occurrences = planner.resolve_affected_occurrences(
        faculty_id=SHARMA_ID,
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
    )
    res_feasible = planner.plan(occurrences)
    assert res_feasible.feasible_status == FeasibilityStatusEnum.feasible
    assert res_feasible.plans[0].coverage_percentage == 100.0

    # 2. Infeasible / Empty
    res_empty = planner.plan([])
    assert res_empty.feasible_status == FeasibilityStatusEnum.infeasible
    assert res_empty.total_affected_occurrences == 0


def test_partial_scenario_uncovered_explanations():
    """
    When candidate availability is constrained, the solver returns a partial plan
    with explicit uncovered explanations (never silently dropping classes).
    """
    mock_gen = MagicMock(spec=CandidateGenerator)
    f1 = uuid.uuid4()
    mock_faculty = MagicMock(spec=Faculty, id=f1, name="Dr. OnlyCandidate", weekly_max_hours=1.0)
    mock_gen.faculty_map = {f1: mock_faculty}
    mock_gen.get_assigned_hours_for_week.return_value = 0.0

    # Two occurrences in the same period on the same date: candidate can only cover one!
    o1_id, o2_id = uuid.uuid4(), uuid.uuid4()
    p_id = uuid.uuid4()

    mock_period = MagicMock(spec=Period, id=p_id, label="P1", duration_hours=1.0)
    mock_period.start_time.strftime.return_value = "09:00"
    mock_period.end_time.strftime.return_value = "10:00"

    mock_entry1 = MagicMock(spec=TimetableEntry, faculty_id=uuid.uuid4(), period_id=p_id, period=mock_period)
    mock_entry1.course.id = uuid.uuid4()
    mock_entry1.course.code = "CS101"
    mock_entry1.course.name = "Intro to CS"
    mock_entry1.section.id = uuid.uuid4()
    mock_entry1.section.name = "CS-1A"
    mock_entry1.room.id = uuid.uuid4()
    mock_entry1.room.name = "Room 101"

    mock_entry2 = MagicMock(spec=TimetableEntry, faculty_id=uuid.uuid4(), period_id=p_id, period=mock_period)
    mock_entry2.course.id = uuid.uuid4()
    mock_entry2.course.code = "CS102"
    mock_entry2.course.name = "Data Structures"
    mock_entry2.section.id = uuid.uuid4()
    mock_entry2.section.name = "CS-1B"
    mock_entry2.room.id = uuid.uuid4()
    mock_entry2.room.name = "Room 102"

    occ1 = MagicMock(spec=ClassOccurrence, id=o1_id, occurrence_date=date(2026, 11, 2), timetable_entry=mock_entry1)
    occ2 = MagicMock(spec=ClassOccurrence, id=o2_id, occurrence_date=date(2026, 11, 2), timetable_entry=mock_entry2)

    cand = MagicMock(spec=CandidateEligibility, faculty_id=f1, faculty_name="Dr. OnlyCandidate", total_soft_score=0.8, soft_scores={"SP-01": 0.8})

    elig1 = MagicMock(eligible_candidates=[cand])
    elig2 = MagicMock(eligible_candidates=[cand])

    mock_gen.get_occurrence_eligibility.side_effect = lambda occ, **kwargs: elig1 if occ.id == o1_id else elig2

    solver = CPSATSolver(mock_gen)
    plan = solver.solve([occ1, occ2])

    assert plan.total_occurrences == 2
    assert plan.covered_occurrences == 1
    assert plan.uncovered_count == 1
    assert len(plan.uncovered_assignments) == 1
    assert plan.uncovered_assignments[0].is_covered is False
    assert plan.uncovered_assignments[0].uncovered_reason is not None


# ── API Endpoint Tests ────────────────────────────────────────────────────


def test_post_optimize_unauthenticated(client: TestClient):
    """POST /planner/optimize returns 401 without token."""
    response = client.post("/planner/optimize", json={})
    assert response.status_code == 401


def test_post_optimize_hero_scenario(seeded_client: TestClient):
    """
    POST /planner/optimize with Hero scenario credentials returns 100% feasible
    CP-SAT replacement plans and greedy baseline.
    """
    login_res = seeded_client.post(
        "/auth/token",
        data={"username": "principal@campus.os", "password": "changeme"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    payload = {
        "faculty_id": str(SHARMA_ID),
        "start_date": "2026-11-02",
        "end_date": "2026-11-04",
        "max_alternatives": 3,
    }

    response = seeded_client.post(
        "/planner/optimize",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["feasible_status"] == "feasible"
    assert body["total_affected_occurrences"] == 6
    assert len(body["plans"]) >= 2
    assert body["baseline_greedy_plan"] is not None

    primary_plan = body["plans"][0]
    assert primary_plan["coverage_percentage"] == 100.0
    assert primary_plan["covered_occurrences"] == 6
    assert len(primary_plan["assignments"]) == 6
    assert primary_plan["is_valid"] is True
    assert primary_plan["solve_time_ms"] > 0.0


def test_post_optimize_not_found(seeded_client: TestClient):
    """POST /planner/optimize with non-existent criteria returns 404."""
    login_res = seeded_client.post(
        "/auth/token",
        data={"username": "principal@campus.os", "password": "changeme"},
    )
    token = login_res.json()["access_token"]

    payload = {
        "faculty_id": str(uuid.uuid4()),  # Random unknown faculty
        "start_date": "2030-01-01",
        "end_date": "2030-01-02",
    }

    response = seeded_client.post(
        "/planner/optimize",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_get_occurrence_eligibility_endpoint(seeded_client: TestClient):
    """GET /planner/eligibility/{occurrence_id} returns candidate pool analysis."""
    login_res = seeded_client.post(
        "/auth/token",
        data={"username": "hod.cs@campus.os", "password": "changeme"},
    )
    token = login_res.json()["access_token"]

    # First fetch an occurrence ID from conflicts or DB
    conflicts_res = seeded_client.get(
        "/conflicts?date=2026-11-02",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert conflicts_res.status_code == 200
    hc03_violations = conflicts_res.json()["by_rule"].get("HC-03", [])
    assert len(hc03_violations) > 0

    # Get occurrence ID from affected entities
    occ_id = None
    for v in hc03_violations:
        for ref in v["evidence_refs"]:
            if ref["ref_type"] == "class_occurrence":
                occ_id = ref["ref_id"]
                break
        if occ_id:
            break

    assert occ_id is not None

    elig_res = seeded_client.get(
        f"/planner/eligibility/{occ_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert elig_res.status_code == 200
    body = elig_res.json()
    assert body["occurrence_id"] == occ_id
    assert body["eligible_count"] > 0
    assert len(body["eligible_candidates"]) > 0
    assert len(body["ineligible_candidates"]) > 0
