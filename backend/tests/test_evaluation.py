"""
Tests for Reproducible Evaluation Harness and Hardening (Milestone M7).

Verifies:
- Scenarios suite size >= 50 across CS, EC, ME departments
- Zero newly introduced hard violations invariant (Safety target)
- Correct distinction between feasible, partial, and infeasible scenarios
- Comparative metrics (CP-SAT vs Greedy)
- Evaluation artifact generation (evaluation_results.json, docs/EVALUATION.md)
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

# Ensure root directory is in sys.path so scripts.evaluate can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.orm import Session

from app.db.models import Faculty
from app.engine.planner import JointOptimizationPlanner
from scripts.evaluate import (
    ScenarioSpec,
    build_scenario_suite,
    calculate_workload_metrics,
    evaluate_scenario,
)


def test_evaluation_scenario_suite_size(db_session: Session):
    """Verify that benchmark scenario suite has >= 50 diverse scenarios across 3 departments."""
    scenarios = build_scenario_suite(db_session)
    assert len(scenarios) >= 50
    assert len(scenarios) == 55

    categories = set(s.category for s in scenarios)
    assert "Hero Scenario" in categories
    assert "Single-Day Leave" in categories
    assert "Multi-Day Leave" in categories
    assert "Full-Week Leave" in categories
    assert "Specialty / Bottleneck" in categories
    assert "High-Pressure / Simultaneous" in categories


def test_hero_scenario_cpsat_vs_greedy(db_session: Session):
    """Test Hero Scenario (Dr. Raj Sharma CS001 Nov 2-4): 6 affected classes, 100% coverage."""
    planner = JointOptimizationPlanner(db_session)
    hero_spec = ScenarioSpec(
        id="SC-01",
        name="Hero Scenario: Dr. Raj Sharma Leave",
        category="Hero Scenario",
        faculty_codes=["CS001"],
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
        description="Hero scenario test",
    )
    result = evaluate_scenario(planner, db_session, hero_spec)

    assert result.affected_classes == 6
    assert result.cpsat_covered == 6
    assert result.cpsat_coverage_pct == 100.0
    assert result.cpsat_status == "feasible_complete"
    assert result.cpsat_new_hard_violations == 0
    assert result.cpsat_is_valid is True
    assert result.cpsat_alternatives_count >= 1

    assert result.greedy_covered == 6
    assert result.greedy_new_hard_violations == 0
    assert result.greedy_is_valid is True


def test_infeasible_specialty_scenario_safety(db_session: Session):
    """Test specialty bottleneck scenario (CS003 Dr. Arun Kumar, sole expert in operating_systems)."""
    planner = JointOptimizationPlanner(db_session)
    spec = ScenarioSpec(
        id="SC-03",
        name="Single-Day: CS003 on Mon Nov 02",
        category="Single-Day Leave",
        faculty_codes=["CS003"],
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 2),
        description="Dr. Arun Kumar sole OS expert",
    )
    result = evaluate_scenario(planner, db_session, spec)

    # CS003 has 3 classes on Mon Nov 02, including Operating Systems
    assert result.affected_classes == 3
    # System must honestly report infeasible rather than assign unqualified faculty
    assert result.cpsat_status == "infeasible"
    assert result.cpsat_covered == 0
    # Safety invariant: 0 new hard violations introduced
    assert result.cpsat_new_hard_violations == 0
    assert result.cpsat_is_valid is True


def test_zero_affected_occurrences_handling(db_session: Session):
    """Test scenario where faculty has no classes on that day (graceful 0 affected occurrences)."""
    planner = JointOptimizationPlanner(db_session)
    spec = ScenarioSpec(
        id="SC-ZERO",
        name="Zero Load Test",
        category="Single-Day Leave",
        faculty_codes=["EC001"],
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 2),
        description="Faculty has no classes on Monday Nov 02",
    )
    result = evaluate_scenario(planner, db_session, spec)

    assert result.affected_classes == 0
    assert result.cpsat_status == "feasible_complete"
    assert result.cpsat_covered == 0
    assert result.cpsat_new_hard_violations == 0


def test_safety_target_zero_new_hard_violations_on_benchmark_sample(db_session: Session):
    """
    Evaluates a diverse 10-scenario benchmark sample and strictly verifies
    that zero new hard violations are introduced in all validated plans.
    """
    planner = JointOptimizationPlanner(db_session)
    all_scenarios = build_scenario_suite(db_session)

    # Sample representative scenarios across categories
    sample = all_scenarios[:10]
    for sc in sample:
        res = evaluate_scenario(planner, db_session, sc)
        # Non-negotiable invariant: zero newly introduced hard violations
        assert res.cpsat_new_hard_violations == 0, f"CP-SAT introduced hard violations in {sc.id}"
        assert res.greedy_new_hard_violations == 0, f"Greedy introduced hard violations in {sc.id}"


def test_workload_metric_calculation():
    """Verify that calculate_workload_metrics correctly calculates stddev and max hours."""
    from app.schemas.planner import AssignmentProposal, OptimizationPlan, SolverStatusEnum

    proposals = [
        AssignmentProposal(
            occurrence_id="10000000-0000-0000-0000-000000000001",
            occurrence_date="2026-11-02",
            period_id="20000000-0000-0000-0000-000000000001",
            period_label="P1",
            period_time_range="09:00 - 10:00",
            start_time="09:00",
            end_time="10:00",
            course_id="30000000-0000-0000-0000-000000000001",
            course_code="CS101",
            course_name="Intro to CS",
            section_id="40000000-0000-0000-0000-000000000001",
            section_name="CS-1A",
            room_id="50000000-0000-0000-0000-000000000001",
            room_name="Room 101",
            original_faculty_id="60000000-0000-0000-0000-000000000001",
            original_faculty_name="Dr. Raj Sharma",
            assigned_faculty_id="60000000-0000-0000-0000-000000000002",
            assigned_faculty_name="Dr. Priya Patel",
            score_breakdown={},
            total_score=85.0,
            is_covered=True,
        ),
        AssignmentProposal(
            occurrence_id="10000000-0000-0000-0000-000000000002",
            occurrence_date="2026-11-02",
            period_id="20000000-0000-0000-0000-000000000002",
            period_label="P2",
            period_time_range="10:00 - 11:00",
            start_time="10:00",
            end_time="11:00",
            course_id="30000000-0000-0000-0000-000000000001",
            course_code="CS101",
            course_name="Intro to CS",
            section_id="40000000-0000-0000-0000-000000000001",
            section_name="CS-1A",
            room_id="50000000-0000-0000-0000-000000000001",
            room_name="Room 101",
            original_faculty_id="60000000-0000-0000-0000-000000000001",
            original_faculty_name="Dr. Raj Sharma",
            assigned_faculty_id="60000000-0000-0000-0000-000000000003",
            assigned_faculty_name="Dr. Sunita Mehta",
            score_breakdown={},
            total_score=80.0,
            is_covered=True,
        ),
    ]

    plan = OptimizationPlan(
        plan_id="test_plan",
        plan_name="Test Plan",
        description="Testing workload stddev",
        solver_type="cp_sat",
        solver_status=SolverStatusEnum.optimal,
        solve_time_ms=12.5,
        total_occurrences=2,
        covered_occurrences=2,
        uncovered_count=0,
        coverage_percentage=100.0,
        overall_score=82.5,
        score_breakdown={},
        assignments=proposals,
        uncovered_assignments=[],
        is_valid=True,
    )

    stddev, max_h = calculate_workload_metrics(plan)
    # 2 different faculty, 1 class each -> counts = [1, 1], stddev = 0.0, max_h = 1.0
    assert stddev == 0.0
    assert max_h == 1.0


def test_evaluation_generated_reports_exist():
    """Verify that evaluation artifacts evaluation_results.json and docs/EVALUATION.md exist and are valid."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    json_path = root_dir / "evaluation_results.json"
    md_path = root_dir / "docs" / "EVALUATION.md"

    assert json_path.exists(), "evaluation_results.json should exist"
    assert md_path.exists(), "docs/EVALUATION.md should exist"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_scenarios"] == 55
    assert "benchmark_summary" in data
    assert "cpsat" in data["benchmark_summary"]
    assert "greedy" in data["benchmark_summary"]
    assert data["benchmark_summary"]["cpsat"]["new_hard_violations"] == 0
    assert data["benchmark_summary"]["greedy"]["new_hard_violations"] == 0

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    assert "# Campus OS — Empirical Evaluation Report (Milestone M7)" in md_text
    assert "Google OR-Tools CP-SAT Planner" in md_text
    assert "Greedy Heuristic Baseline" in md_text
    assert "Zero newly introduced hard violations" in md_text
