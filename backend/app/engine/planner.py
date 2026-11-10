"""
High-Level Joint Optimization Planner (Milestone M3).

Coordinates:
- Resolution of affected class occurrences
- Candidate eligibility generation
- CP-SAT multi-alternative joint optimization
- Greedy baseline benchmark comparison
- Independent validation via RuleEngine (zero new hard violations)
- Feasibility classification (feasible, partial, infeasible)
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Sequence

from sqlalchemy.orm import Session, joinedload

from app.db.models import ClassOccurrence, Faculty, Period, Room, Section, TimetableEntry
from app.engine.eligibility import CandidateGenerator
from app.engine.rules import RuleEngine
from app.engine.solver import CPSATSolver, GreedyBaselineSolver
from app.schemas.planner import (
    FeasibilityStatusEnum,
    OptimizationPlan,
    PlannerResponse,
    SolverStatusEnum,
)
from app.schemas.rules import ConstraintTypeEnum


class JointOptimizationPlanner:
    """
    High-level orchestration service for joint timetable optimization.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.candidate_gen = CandidateGenerator(db)
        self.cpsat_solver = CPSATSolver(self.candidate_gen)
        self.greedy_solver = GreedyBaselineSolver(self.candidate_gen)
        self.rule_engine = RuleEngine(db)

    def resolve_affected_occurrences(
        self,
        occurrence_ids: list[uuid.UUID] | None = None,
        faculty_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ClassOccurrence]:
        """
        Resolve the affected class occurrences from DB either by explicit IDs
        or by affected faculty member and date range.
        """
        query = (
            self.db.query(ClassOccurrence)
            .options(
                joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.period),
                joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.course),
                joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.section),
                joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.room),
            )
            .filter(ClassOccurrence.status != "cancelled")
        )

        if occurrence_ids:
            return query.filter(ClassOccurrence.id.in_(occurrence_ids)).all()

        if faculty_id:
            query = query.join(ClassOccurrence.timetable_entry).filter(
                TimetableEntry.faculty_id == faculty_id
            )

        if start_date:
            query = query.filter(ClassOccurrence.occurrence_date >= start_date)
        if end_date:
            query = query.filter(ClassOccurrence.occurrence_date <= end_date)

        return query.order_by(ClassOccurrence.occurrence_date).all()

    def validate_proposed_plan(
        self,
        plan: OptimizationPlan,
        all_occurrences_in_scope: Sequence[ClassOccurrence],
    ) -> OptimizationPlan:
        """
        Independently validate proposed plan using RuleEngine.
        Creates an isolated in-memory representation with proposed override_faculty_ids
        and verifies that no new hard violations are introduced.
        """
        # Create map of proposed replacements
        replacement_map = {
            a.occurrence_id: a.assigned_faculty_id
            for a in plan.assignments
            if a.assigned_faculty_id is not None
        }

        # Build simulated in-memory occurrence list
        class SimulatedOccurrence:
            def __init__(self, original: ClassOccurrence, override_fid: uuid.UUID | None):
                self.id = original.id
                self.occurrence_date = original.occurrence_date
                self.timetable_entry = original.timetable_entry
                self.faculty_id = original.timetable_entry.faculty_id
                self.effective_faculty_id = override_fid or original.effective_faculty_id
                self.effective_room_id = original.effective_room_id
                self.period_id = original.timetable_entry.period_id

        simulated_list = [
            SimulatedOccurrence(occ, replacement_map.get(occ.id))
            for occ in all_occurrences_in_scope
        ]

        # 1. Baseline validation on original occurrences
        baseline_result = self.rule_engine.validate_dated_occurrences(
            occurrences=all_occurrences_in_scope,
        )

        # 2. Proposed validation on simulated occurrences
        proposed_result = self.rule_engine.validate_dated_occurrences(
            occurrences=simulated_list,
        )

        # 3. HC-09 state diffing: check that zero new hard violations are introduced
        comparison = self.rule_engine.compare_states(
            baseline_violations=baseline_result.violations,
            proposed_violations=proposed_result.violations,
        )

        plan.is_valid = not comparison.introduces_new_hard_violations
        plan.validation_result = proposed_result
        return plan

    def plan(
        self,
        occurrences: Sequence[ClassOccurrence],
        max_alternatives: int = 3,
        weights: dict[str, float] | None = None,
    ) -> PlannerResponse:
        """
        Execute full candidate generation and optimization workflow.
        """
        total_affected = len(occurrences)
        if total_affected == 0:
            return PlannerResponse(
                scenario_summary="No affected class occurrences specified or found.",
                feasible_status=FeasibilityStatusEnum.infeasible,
                total_affected_occurrences=0,
                plans=[],
                baseline_greedy_plan=None,
                candidate_pool_size=len(self.candidate_gen.all_faculty),
            )

        # 1. Generate CP-SAT Plans (up to 3 distinct alternatives)
        cpsat_plans = self.cpsat_solver.solve_alternatives(
            occurrences,
            max_alternatives=max_alternatives,
            user_weights=weights,
        )

        # 2. Generate Greedy Baseline Plan
        greedy_plan = self.greedy_solver.solve(occurrences, weights=weights)

        # 3. Independently validate all generated plans
        validated_cpsat_plans = [
            self.validate_proposed_plan(p, occurrences) for p in cpsat_plans
        ]
        validated_greedy_plan = self.validate_proposed_plan(greedy_plan, occurrences)

        # 4. Determine feasibility status based on primary plan
        if validated_cpsat_plans:
            primary_plan = validated_cpsat_plans[0]
            if primary_plan.covered_occurrences == total_affected:
                feasibility = FeasibilityStatusEnum.feasible
            elif primary_plan.covered_occurrences > 0:
                feasibility = FeasibilityStatusEnum.partial
            else:
                feasibility = FeasibilityStatusEnum.infeasible
        elif validated_greedy_plan and validated_greedy_plan.covered_occurrences > 0:
            feasibility = FeasibilityStatusEnum.partial
        else:
            feasibility = FeasibilityStatusEnum.infeasible

        summary = (
            f"Evaluated {total_affected} affected class occurrences against "
            f"{len(self.candidate_gen.all_faculty)} candidate faculty members. "
            f"Generated {len(validated_cpsat_plans)} feasible CP-SAT plan(s) "
            f"and 1 greedy baseline."
        )

        return PlannerResponse(
            scenario_summary=summary,
            feasible_status=feasibility,
            total_affected_occurrences=total_affected,
            plans=validated_cpsat_plans,
            baseline_greedy_plan=validated_greedy_plan,
            candidate_pool_size=len(self.candidate_gen.all_faculty),
        )
