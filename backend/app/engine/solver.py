"""
Joint Optimization Solver and Greedy Baseline (Milestone M3).

Implements:
1. CPSATSolver: Joint multi-class replacement optimization using Google OR-Tools CP-SAT.
   - Enforces coverage, overlap prevention, and cumulative workload capacity.
   - Multi-objective lexicographic optimization: (1) Maximize coverage, (2) Maximize soft preferences.
   - Distinct alternative plan generation (up to 3 distinct feasible plans).
2. GreedyBaselineSolver: Greedy heuristic baseline for algorithmic benchmarking.
"""
from __future__ import annotations

import collections
import time
import uuid
from datetime import date
from typing import Any, Sequence

from ortools.sat.python import cp_model

from app.db.models import ClassOccurrence, Faculty, Period
from app.engine.eligibility import CandidateGenerator
from app.schemas.planner import (
    AssignmentProposal,
    CandidateEligibility,
    OptimizationPlan,
    SolverStatusEnum,
)


class CPSATSolver:
    """
    Joint optimization planner powered by OR-Tools CP-SAT.
    """

    def __init__(self, candidate_gen: CandidateGenerator) -> None:
        self.candidate_gen = candidate_gen
        self.faculty_map = candidate_gen.faculty_map

    def solve(
        self,
        occurrences: Sequence[ClassOccurrence],
        plan_id: str = "plan_a",
        plan_name: str = "Optimal Plan (Balanced)",
        description: str = "Standard joint optimization balancing expertise, workload, continuity, and department.",
        weights: dict[str, float] | None = None,
        exclude_solutions: list[dict[uuid.UUID, uuid.UUID]] | None = None,
    ) -> OptimizationPlan:
        """
        Solve joint assignment for given occurrences.
        exclude_solutions: optional list of previous assignments {occ_id: fac_id} to exclude for distinct alternatives.
        """
        start_time = time.perf_counter()

        model = cp_model.CpModel()

        # Pre-compute eligibility for each occurrence
        occ_eligibility_map: dict[uuid.UUID, list[CandidateEligibility]] = {}
        for occ in occurrences:
            elig = self.candidate_gen.get_occurrence_eligibility(occ, weights=weights)
            occ_eligibility_map[occ.id] = elig.eligible_candidates

        # Decision variables: x[(occ_id, fac_id)] in {0, 1}
        x: dict[tuple[uuid.UUID, uuid.UUID], cp_model.IntVar] = {}
        vars_by_occ: dict[uuid.UUID, list[cp_model.IntVar]] = collections.defaultdict(list)
        vars_by_fac_week: dict[tuple[uuid.UUID, date], list[tuple[cp_model.IntVar, float]]] = collections.defaultdict(list)

        for occ in occurrences:
            eligible_candidates = occ_eligibility_map[occ.id]
            period = occ.timetable_entry.period
            duration = period.duration_hours if period else 1.0
            from app.engine.rules import get_calendar_week_bounds
            week_start, _ = get_calendar_week_bounds(occ.occurrence_date)

            for cand in eligible_candidates:
                var = model.NewBoolVar(f"x_{occ.id}_{cand.faculty_id}")
                x[(occ.id, cand.faculty_id)] = var
                vars_by_occ[occ.id].append(var)
                vars_by_fac_week[(cand.faculty_id, week_start)].append((var, duration))

        # Constraint 1: At most 1 faculty per occurrence
        for occ in occurrences:
            var_list = vars_by_occ.get(occ.id, [])
            if var_list:
                model.Add(sum(var_list) <= 1)

        # Constraint 2: No double booking across overlapping occurrences
        # If occurrence i and k have same date and same period (or overlapping times), a faculty cannot cover both
        n = len(occurrences)
        for i in range(n):
            occ_i = occurrences[i]
            pid_i = occ_i.timetable_entry.period_id
            date_i = occ_i.occurrence_date
            for k in range(i + 1, n):
                occ_k = occurrences[k]
                if occ_k.occurrence_date == date_i and occ_k.timetable_entry.period_id == pid_i:
                    # Same date, same period! Check shared candidates
                    cands_i = {c.faculty_id for c in occ_eligibility_map[occ_i.id]}
                    cands_k = {c.faculty_id for c in occ_eligibility_map[occ_k.id]}
                    shared = cands_i & cands_k
                    for fac_id in shared:
                        var_i = x.get((occ_i.id, fac_id))
                        var_k = x.get((occ_k.id, fac_id))
                        if var_i is not None and var_k is not None:
                            model.Add(var_i + var_k <= 1)

        # Constraint 3: Cumulative workload limits across the week
        # (current_assigned_hours + sum(duration_i * x_ij)) <= weekly_max_hours
        # Scale by 100 to use integer arithmetic in CP-SAT
        for (fac_id, week_start), var_dur_pairs in vars_by_fac_week.items():
            fac = self.faculty_map.get(fac_id)
            if not fac:
                continue
            current_hours = self.candidate_gen.get_assigned_hours_for_week(fac_id, week_start)
            max_hours = fac.weekly_max_hours
            available_hours = max(0.0, max_hours - current_hours)
            available_scaled = int(round(available_hours * 100))

            terms = [int(round(dur * 100)) * var for var, dur in var_dur_pairs]
            model.Add(sum(terms) <= available_scaled)

        # Exclusion constraints for distinct alternatives:
        if exclude_solutions:
            for past_sol in exclude_solutions:
                # Past solution has {(occ_id, fac_id)} assignments
                matching_vars = [
                    x[(occ_id, fac_id)]
                    for occ_id, fac_id in past_sol.items()
                    if (occ_id, fac_id) in x
                ]
                if len(matching_vars) == len(past_sol) and len(matching_vars) > 0:
                    # Enforce that the new plan differs in at least 1 assignment
                    model.Add(sum(matching_vars) <= len(matching_vars) - 1)

        # Objective Function:
        # Lexicographical: Each assigned occurrence gets COVERAGE_WEIGHT (100,000)
        # plus scaled soft score (0 to 1,000).
        COVERAGE_WEIGHT = 100_000
        obj_terms = []

        for occ in occurrences:
            for cand in occ_eligibility_map[occ.id]:
                var = x.get((occ.id, cand.faculty_id))
                if var is not None:
                    soft_scaled = int(round(cand.total_soft_score * 1000))
                    obj_terms.append(var * (COVERAGE_WEIGHT + soft_scaled))

        if obj_terms:
            model.Maximize(sum(obj_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        status_code = solver.Solve(model)

        solve_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        status_map = {
            cp_model.OPTIMAL: SolverStatusEnum.optimal,
            cp_model.FEASIBLE: SolverStatusEnum.feasible,
            cp_model.INFEASIBLE: SolverStatusEnum.infeasible,
            cp_model.MODEL_INVALID: SolverStatusEnum.model_invalid,
            cp_model.UNKNOWN: SolverStatusEnum.unknown,
        }
        solver_status = status_map.get(status_code, SolverStatusEnum.unknown)

        assignments: list[AssignmentProposal] = []
        uncovered: list[AssignmentProposal] = []
        total_soft_score_sum = 0.0
        score_breakdown_accum: dict[str, float] = collections.defaultdict(float)

        if solver_status in (SolverStatusEnum.optimal, SolverStatusEnum.feasible):
            for occ in occurrences:
                entry = occ.timetable_entry
                period = entry.period
                course = entry.course
                section = entry.section
                room = entry.room
                orig_fac = self.faculty_map.get(entry.faculty_id)
                orig_fac_name = orig_fac.name if orig_fac else "Unknown"

                assigned_cand: CandidateEligibility | None = None
                for cand in occ_eligibility_map[occ.id]:
                    var = x.get((occ.id, cand.faculty_id))
                    if var is not None and solver.Value(var) == 1:
                        assigned_cand = cand
                        break

                time_str = f"{period.start_time.strftime('%H:%M')}–{period.end_time.strftime('%H:%M')}"

                if assigned_cand:
                    total_soft_score_sum += assigned_cand.total_soft_score
                    for k, v in assigned_cand.soft_scores.items():
                        score_breakdown_accum[k] += v

                    proposal = AssignmentProposal(
                        occurrence_id=occ.id,
                        occurrence_date=occ.occurrence_date,
                        period_id=period.id,
                        period_label=period.label,
                        period_time_range=time_str,
                        course_id=course.id,
                        course_code=course.code,
                        course_name=course.name,
                        section_id=section.id,
                        section_name=section.name,
                        room_id=room.id,
                        room_name=room.name,
                        original_faculty_id=entry.faculty_id,
                        original_faculty_name=orig_fac_name,
                        assigned_faculty_id=assigned_cand.faculty_id,
                        assigned_faculty_name=assigned_cand.faculty_name,
                        is_covered=True,
                        uncovered_reason=None,
                        soft_score=assigned_cand.total_soft_score,
                        score_breakdown=assigned_cand.soft_scores,
                    )
                    assignments.append(proposal)
                else:
                    # Uncovered class
                    reasons = []
                    for c in occ_eligibility_map[occ.id]:
                        reasons.append(f"{c.faculty_name}: busy in solver schedule")
                    reason_str = "No eligible candidate available within joint constraints" if not occ_eligibility_map[occ.id] else "Candidates exhausted by overlapping joint assignments"

                    uncovered_proposal = AssignmentProposal(
                        occurrence_id=occ.id,
                        occurrence_date=occ.occurrence_date,
                        period_id=period.id,
                        period_label=period.label,
                        period_time_range=time_str,
                        course_id=course.id,
                        course_code=course.code,
                        course_name=course.name,
                        section_id=section.id,
                        section_name=section.name,
                        room_id=room.id,
                        room_name=room.name,
                        original_faculty_id=entry.faculty_id,
                        original_faculty_name=orig_fac_name,
                        assigned_faculty_id=None,
                        assigned_faculty_name=None,
                        is_covered=False,
                        uncovered_reason=reason_str,
                        soft_score=0.0,
                        score_breakdown={},
                    )
                    uncovered.append(uncovered_proposal)
        else:
            # Entirely infeasible
            for occ in occurrences:
                entry = occ.timetable_entry
                period = entry.period
                course = entry.course
                section = entry.section
                room = entry.room
                orig_fac = self.faculty_map.get(entry.faculty_id)
                time_str = f"{period.start_time.strftime('%H:%M')}–{period.end_time.strftime('%H:%M')}"
                uncovered.append(
                    AssignmentProposal(
                        occurrence_id=occ.id,
                        occurrence_date=occ.occurrence_date,
                        period_id=period.id,
                        period_label=period.label,
                        period_time_range=time_str,
                        course_id=course.id,
                        course_code=course.code,
                        course_name=course.name,
                        section_id=section.id,
                        section_name=section.name,
                        room_id=room.id,
                        room_name=room.name,
                        original_faculty_id=entry.faculty_id,
                        original_faculty_name=orig_fac.name if orig_fac else "Unknown",
                        assigned_faculty_id=None,
                        assigned_faculty_name=None,
                        is_covered=False,
                        uncovered_reason="CP-SAT solver could not find a feasible joint assignment",
                        soft_score=0.0,
                        score_breakdown={},
                    )
                )

        covered_count = len(assignments)
        total_count = len(occurrences)
        coverage_pct = round((covered_count / max(total_count, 1)) * 100.0, 1)

        # Average normalized quality score [0.0, 100.0]
        avg_soft = (total_soft_score_sum / max(covered_count, 1)) if covered_count > 0 else 0.0
        # Combine coverage and quality into an aggregate score: coverage (70%) + soft quality (30%)
        overall_score = round((coverage_pct * 0.70) + (avg_soft * 100.0 * 0.30), 1)

        avg_breakdown: dict[str, float] = {}
        for k, v in score_breakdown_accum.items():
            avg_breakdown[k] = round(v / max(covered_count, 1), 3)

        return OptimizationPlan(
            plan_id=plan_id,
            plan_name=plan_name,
            description=description,
            solver_type="cp_sat",
            solver_status=solver_status,
            solve_time_ms=solve_time_ms,
            total_occurrences=total_count,
            covered_occurrences=covered_count,
            uncovered_count=len(uncovered),
            coverage_percentage=coverage_pct,
            overall_score=overall_score,
            score_breakdown=avg_breakdown,
            assignments=assignments,
            uncovered_assignments=uncovered,
            is_valid=(solver_status in (SolverStatusEnum.optimal, SolverStatusEnum.feasible)),
            validation_result=None,
        )

    def solve_alternatives(
        self,
        occurrences: Sequence[ClassOccurrence],
        max_alternatives: int = 3,
        user_weights: dict[str, float] | None = None,
    ) -> list[OptimizationPlan]:
        """
        Generate up to 3 distinct feasible plans with transparent criteria.
        """
        plans: list[OptimizationPlan] = []
        known_solutions: list[dict[uuid.UUID, uuid.UUID]] = []

        # Configuration 1: Balanced (Standard)
        weights_a = user_weights or {"SP-01": 0.35, "SP-02": 0.30, "SP-03": 0.25, "SP-04": 0.10}
        plan_a = self.solve(
            occurrences,
            plan_id="plan_a",
            plan_name="Optimal Plan (Balanced)",
            description="Optimal joint schedule balancing subject expertise, workload distribution, and teaching continuity.",
            weights=weights_a,
        )
        if plan_a.solver_status in (SolverStatusEnum.optimal, SolverStatusEnum.feasible) and plan_a.covered_occurrences > 0:
            plans.append(plan_a)
            sol_a = {a.occurrence_id: a.assigned_faculty_id for a in plan_a.assignments if a.assigned_faculty_id}
            known_solutions.append(sol_a)

        if max_alternatives <= 1 or not known_solutions:
            return plans

        # Configuration 2: Department & Continuity Focused
        weights_b = {"SP-01": 0.15, "SP-02": 0.10, "SP-03": 0.35, "SP-04": 0.40}
        plan_b = self.solve(
            occurrences,
            plan_id="plan_b",
            plan_name="Continuity & Department Focus",
            description="Prioritizes faculty from the same department and existing cohort familiarity.",
            weights=weights_b,
            exclude_solutions=known_solutions,
        )
        if plan_b.solver_status in (SolverStatusEnum.optimal, SolverStatusEnum.feasible) and plan_b.covered_occurrences > 0:
            sol_b = {a.occurrence_id: a.assigned_faculty_id for a in plan_b.assignments if a.assigned_faculty_id}
            if sol_b not in known_solutions:
                plans.append(plan_b)
                known_solutions.append(sol_b)

        if len(plans) >= max_alternatives:
            return plans

        # Configuration 3: Workload Balancing Focused
        weights_c = {"SP-01": 0.15, "SP-02": 0.60, "SP-03": 0.15, "SP-04": 0.10}
        plan_c = self.solve(
            occurrences,
            plan_id="plan_c",
            plan_name="Workload Distribution Focus",
            description="Prioritizes faculty with lowest current utilization to avoid burnout.",
            weights=weights_c,
            exclude_solutions=known_solutions,
        )
        if plan_c.solver_status in (SolverStatusEnum.optimal, SolverStatusEnum.feasible) and plan_c.covered_occurrences > 0:
            sol_c = {a.occurrence_id: a.assigned_faculty_id for a in plan_c.assignments if a.assigned_faculty_id}
            if sol_c not in known_solutions:
                plans.append(plan_c)

        return plans


class GreedyBaselineSolver:
    """
    Greedy baseline algorithm for comparative benchmarking against CP-SAT.
    Processes occurrences chronologically and assigns the best candidate greedily.
    """

    def __init__(self, candidate_gen: CandidateGenerator) -> None:
        self.candidate_gen = candidate_gen
        self.faculty_map = candidate_gen.faculty_map

    def solve(
        self,
        occurrences: Sequence[ClassOccurrence],
        weights: dict[str, float] | None = None,
    ) -> OptimizationPlan:
        start_time = time.perf_counter()

        # Sort chronologically by date and start time
        sorted_occs = sorted(
            occurrences,
            key=lambda o: (
                o.occurrence_date,
                o.timetable_entry.period.start_time if o.timetable_entry and o.timetable_entry.period else 0,
            ),
        )

        assignments: list[AssignmentProposal] = []
        uncovered: list[AssignmentProposal] = []

        # Tracking greedy state
        assigned_at_time: dict[tuple[date, uuid.UUID], uuid.UUID] = {}  # (date, period_id) -> fac_id
        added_hours_week: dict[tuple[uuid.UUID, date], float] = collections.defaultdict(float)
        from app.engine.rules import get_calendar_week_bounds

        total_soft_sum = 0.0
        breakdown_accum: dict[str, float] = collections.defaultdict(float)

        for occ in sorted_occs:
            entry = occ.timetable_entry
            period = entry.period
            course = entry.course
            section = entry.section
            room = entry.room
            orig_fac = self.faculty_map.get(entry.faculty_id)
            time_str = f"{period.start_time.strftime('%H:%M')}–{period.end_time.strftime('%H:%M')}"
            dur = period.duration_hours if period else 1.0
            week_start, _ = get_calendar_week_bounds(occ.occurrence_date)

            eligibility = self.candidate_gen.get_occurrence_eligibility(occ, weights=weights)
            # Candidates are already sorted descending by soft score
            chosen: CandidateEligibility | None = None

            for cand in eligibility.eligible_candidates:
                fac = self.faculty_map[cand.faculty_id]
                # 1. Overlap with previous greedy assignment?
                busy_in_greedy = (
                    assigned_at_time.get((occ.occurrence_date, period.id)) == cand.faculty_id
                )
                if busy_in_greedy:
                    continue

                # 2. Exceeds workload with accumulated greedy hours?
                base_hours = self.candidate_gen.get_assigned_hours_for_week(cand.faculty_id, week_start)
                greedy_hours = added_hours_week[(cand.faculty_id, week_start)]
                if base_hours + greedy_hours + dur > fac.weekly_max_hours:
                    continue

                chosen = cand
                break

            if chosen:
                assigned_at_time[(occ.occurrence_date, period.id)] = chosen.faculty_id
                added_hours_week[(chosen.faculty_id, week_start)] += dur
                total_soft_sum += chosen.total_soft_score
                for k, v in chosen.soft_scores.items():
                    breakdown_accum[k] += v

                assignments.append(
                    AssignmentProposal(
                        occurrence_id=occ.id,
                        occurrence_date=occ.occurrence_date,
                        period_id=period.id,
                        period_label=period.label,
                        period_time_range=time_str,
                        course_id=course.id,
                        course_code=course.code,
                        course_name=course.name,
                        section_id=section.id,
                        section_name=section.name,
                        room_id=room.id,
                        room_name=room.name,
                        original_faculty_id=entry.faculty_id,
                        original_faculty_name=orig_fac.name if orig_fac else "Unknown",
                        assigned_faculty_id=chosen.faculty_id,
                        assigned_faculty_name=chosen.faculty_name,
                        is_covered=True,
                        uncovered_reason=None,
                        soft_score=chosen.total_soft_score,
                        score_breakdown=chosen.soft_scores,
                    )
                )
            else:
                uncovered.append(
                    AssignmentProposal(
                        occurrence_id=occ.id,
                        occurrence_date=occ.occurrence_date,
                        period_id=period.id,
                        period_label=period.label,
                        period_time_range=time_str,
                        course_id=course.id,
                        course_code=course.code,
                        course_name=course.name,
                        section_id=section.id,
                        section_name=section.name,
                        room_id=room.id,
                        room_name=room.name,
                        original_faculty_id=entry.faculty_id,
                        original_faculty_name=orig_fac.name if orig_fac else "Unknown",
                        assigned_faculty_id=None,
                        assigned_faculty_name=None,
                        is_covered=False,
                        uncovered_reason="Greedy selection blocked by earlier assignments or workload limits",
                        soft_score=0.0,
                        score_breakdown={},
                    )
                )

        solve_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        covered_count = len(assignments)
        total_count = len(occurrences)
        coverage_pct = round((covered_count / max(total_count, 1)) * 100.0, 1)

        avg_soft = (total_soft_sum / max(covered_count, 1)) if covered_count > 0 else 0.0
        overall_score = round((coverage_pct * 0.70) + (avg_soft * 100.0 * 0.30), 1)

        avg_breakdown: dict[str, float] = {}
        for k, v in breakdown_accum.items():
            avg_breakdown[k] = round(v / max(covered_count, 1), 3)

        return OptimizationPlan(
            plan_id="greedy_baseline",
            plan_name="Greedy Heuristic Baseline",
            description="Sequential greedy assignment without joint global optimization.",
            solver_type="greedy_baseline",
            solver_status=SolverStatusEnum.feasible if covered_count > 0 else SolverStatusEnum.infeasible,
            solve_time_ms=solve_time_ms,
            total_occurrences=total_count,
            covered_occurrences=covered_count,
            uncovered_count=len(uncovered),
            coverage_percentage=coverage_pct,
            overall_score=overall_score,
            score_breakdown=avg_breakdown,
            assignments=assignments,
            uncovered_assignments=uncovered,
            is_valid=True,
            validation_result=None,
        )
