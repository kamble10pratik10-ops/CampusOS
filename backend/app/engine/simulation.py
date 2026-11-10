"""
What-If Simulation Pipeline and Audit Engine (Milestone M4).

Matches SPEC.md Section 8, 9, 11:
- Non-mutating what-if simulation pipeline
- Baseline violation computation
- Multi-plan candidate generation & CP-SAT optimization
- Independent Critic verification
- HC-10 non-mutation verification of operational tables
- Immutable audit record persistence in decision & decision_evidence tables
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.core.permissions import check_department_access
from app.db.models import (
    ClassOccurrence,
    Decision,
    DecisionEvidence,
    DecisionStatusEnum,
    Faculty,
    FacultyLeave,
    RoleEnum,
    TimetableEntry,
    User,
)
from app.engine.critic import Critic
from app.engine.eligibility import CandidateGenerator
from app.engine.planner import JointOptimizationPlanner
from app.engine.rules import RuleEngine
from app.schemas.planner import OptimizationPlan
from app.schemas.rules import ComparisonResult, EvidenceRef
from app.schemas.simulation import (
    CriticResult,
    CriticStatusEnum,
    SimulationRequest,
    SimulationResponse,
)


class SimulationPipeline:
    """
    Executes the 12-step What-If simulation workflow without mutating operational tables.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.planner = JointOptimizationPlanner(db)
        self.candidate_gen = self.planner.candidate_gen
        self.critic = Critic(self.candidate_gen)
        self.rule_engine = RuleEngine(db)

    def run_simulation(
        self,
        request: SimulationRequest,
        current_user: User,
    ) -> SimulationResponse:
        start_time = time.perf_counter()

        # Step 1: Snapshot operational table row counts for HC-10 verification
        snapshot_before = {
            "timetable_entry": self.db.query(TimetableEntry).count(),
            "class_occurrence": self.db.query(ClassOccurrence).count(),
            "faculty": self.db.query(Faculty).count(),
            "faculty_leave": self.db.query(FacultyLeave).count(),
        }

        # Step 2: Resolve affected class occurrences
        if current_user.role == RoleEnum.hod and request.faculty_id:
            target_fac = self.db.get(Faculty, request.faculty_id)
            if target_fac and target_fac.department_id != current_user.department_id:
                check_department_access(current_user, target_fac.department_id)

        occurrences = self.planner.resolve_affected_occurrences(
            occurrence_ids=request.occurrence_ids,
            faculty_id=request.faculty_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        if current_user.role == RoleEnum.hod:
            for occ in occurrences:
                if (
                    occ.timetable_entry
                    and occ.timetable_entry.course
                    and occ.timetable_entry.course.department_id != current_user.department_id
                ):
                    check_department_access(current_user, occ.timetable_entry.course.department_id)

        # Step 3: Compute baseline state & violations
        baseline_validation = self.rule_engine.validate_dated_occurrences(occurrences=occurrences)
        baseline_violations = baseline_validation.violations

        # Step 4: Run CP-SAT joint optimization & greedy baseline
        cpsat_plans = self.planner.cpsat_solver.solve_alternatives(
            occurrences,
            max_alternatives=request.max_alternatives,
            user_weights=request.custom_weights,
        )
        greedy_plan = self.planner.greedy_solver.solve(occurrences, weights=request.custom_weights)

        # Step 5: Critique each plan via Independent Critic
        critiqued_plans: list[OptimizationPlan] = []
        critic_results: list[CriticResult] = []

        for p in cpsat_plans:
            critique_res = self.critic.critique(p, baseline_violations, occurrences)
            p.is_valid = critique_res.is_approved
            critiqued_plans.append(p)
            critic_results.append(critique_res)

        # Critique greedy baseline
        greedy_critique = self.critic.critique(greedy_plan, baseline_violations, occurrences)
        greedy_plan.is_valid = greedy_critique.is_approved

        # Step 6: Select best approved plan (or fallback to first)
        selected_plan: OptimizationPlan | None = None
        selected_critic_result: CriticResult | None = None
        selected_index = 0

        for idx, (p, cr) in enumerate(zip(critiqued_plans, critic_results)):
            if cr.is_approved:
                selected_plan = p
                selected_critic_result = cr
                selected_index = idx
                break

        if not selected_plan and critiqued_plans:
            selected_plan = critiqued_plans[0]
            selected_critic_result = critic_results[0]
        elif not selected_plan:
            selected_plan = greedy_plan
            selected_critic_result = greedy_critique

        # Step 7: Calculate before-and-after state diff
        replacement_map = {
            a.occurrence_id: a.assigned_faculty_id
            for a in selected_plan.assignments
            if a.assigned_faculty_id
        }

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
            for occ in occurrences
        ]

        proposed_validation = self.rule_engine.validate_dated_occurrences(occurrences=simulated_list)
        diff = self.rule_engine.compare_states(
            baseline_violations=baseline_violations,
            proposed_violations=proposed_validation.violations,
        )

        # Step 8: Verify HC-10 non-mutation (ensure operational tables were not modified)
        mutations = self.rule_engine.verify_no_mutation(snapshot_before)
        if mutations:
            raise RuntimeError(f"FATAL HC-10 VIOLATION: Simulation mutated operational database records: {mutations}")

        # Step 9: Collect traceable EvidenceRefs
        evidence_refs: list[EvidenceRef] = []
        if request.faculty_id:
            evidence_refs.append(
                EvidenceRef(
                    ref_type="faculty",
                    ref_id=request.faculty_id,
                    description=f"Primary faculty requesting coverage: {request.faculty_id}",
                )
            )
        for a in selected_plan.assignments:
            if a.assigned_faculty_id:
                evidence_refs.append(
                    EvidenceRef(
                        ref_type="assignment_proposal",
                        ref_id=a.occurrence_id,
                        description=f"Assigned {a.assigned_faculty_name} to {a.course_code} ({a.period_label} on {a.occurrence_date})",
                    )
                )

        # Step 10: Persist immutable audit record in decision and decision_evidence tables
        runtime_ms = int(round((time.perf_counter() - start_time) * 1000))
        decision_id = uuid.uuid4()

        scenario_dept_id = None
        if request.faculty_id:
            fac_rec = self.db.get(Faculty, request.faculty_id)
            if fac_rec:
                scenario_dept_id = str(fac_rec.department_id)
        elif occurrences and occurrences[0].timetable_entry and occurrences[0].timetable_entry.course:
            scenario_dept_id = str(occurrences[0].timetable_entry.course.department_id)
        elif current_user.department_id:
            scenario_dept_id = str(current_user.department_id)

        scenario_payload: dict[str, Any] = {
            "scenario_name": request.scenario_name,
            "faculty_id": str(request.faculty_id) if request.faculty_id else None,
            "department_id": scenario_dept_id,
            "start_date": str(request.start_date) if request.start_date else None,
            "end_date": str(request.end_date) if request.end_date else None,
            "total_affected": len(occurrences),
            "critic_status": selected_critic_result.status.value,
            "coverage_percentage": selected_plan.coverage_percentage,
            "overall_score": selected_plan.overall_score,
            "diff": {
                "existing": len(diff.existing_violations),
                "resolved": len(diff.resolved_violations),
                "new": len(diff.new_violations),
                "remaining": len(diff.remaining_violations),
            },
        }

        audit_decision = Decision(
            id=decision_id,
            scenario=scenario_payload,
            created_by_id=current_user.id,
            decision_status=DecisionStatusEnum.simulation,
            selected_plan_index=selected_index,
            solver_status=selected_plan.solver_status.value,
            llm_status="bypassed_deterministic",
            runtime_ms=runtime_ms,
        )
        self.db.add(audit_decision)

        # Add evidence records
        for ref in evidence_refs[:10]:  # persist key evidence refs
            self.db.add(
                DecisionEvidence(
                    decision_id=decision_id,
                    ref_type=ref.ref_type,
                    ref_id=ref.ref_id,
                    description=ref.description,
                )
            )

        self.db.commit()

        # Step 11: Build limitations and warnings
        limitations = [
            "Simulation is strictly non-mutating: operational timetable records remain unchanged.",
            "Reassignments are proposed for evaluated dated occurrences only and do not alter recurring weekly templates.",
            "Decision recorded in audit system under status 'simulation'. Approval requires explicit administrative action.",
        ]
        if selected_critic_result.status == CriticStatusEnum.feasible_partial:
            limitations.append("Partial coverage: some affected classes could not be covered due to constraint bottlenecks.")

        # Step 12: Return full SimulationResponse
        return SimulationResponse(
            decision_id=decision_id,
            scenario_summary=(
                f"{request.scenario_name}: {selected_plan.covered_occurrences}/{len(occurrences)} classes covered "
                f"({selected_plan.coverage_percentage}%). {selected_critic_result.summary}"
            ),
            scenario_parameters=scenario_payload,
            critic_status=selected_critic_result.status,
            affected_occurrences_count=len(occurrences),
            affected_occurrences=selected_plan.assignments + selected_plan.uncovered_assignments,
            baseline_conflicts_count=len(baseline_violations),
            baseline_violations=baseline_violations,
            alternatives=critiqued_plans,
            selected_plan=selected_plan,
            baseline_greedy_plan=greedy_plan,
            diff=diff,
            critic_result=selected_critic_result,
            evidence_refs=evidence_refs,
            limitations=limitations,
            solver_status=selected_plan.solver_status.value,
            llm_status="bypassed_deterministic",
            created_at=datetime.utcnow(),
            created_by_email=current_user.email,
            decision_status=DecisionStatusEnum.simulation,
        )

