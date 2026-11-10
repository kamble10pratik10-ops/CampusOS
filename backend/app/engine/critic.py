"""
Independent Critic and Trustworthiness Engine (Milestone M4).

Matches SPEC.md Section 9:
- Deterministic multi-angle validation (not an LLM)
- Revalidates all proposed assignments against hard constraints
- Checks for overlapping assignments, applicable leave, and workload limits
- Verifies that claimed coverage counts and scores match computed reality
- Rejects any plan that introduces a new hard violation
- Emits structured issue codes and multi-state status
"""
from __future__ import annotations

import collections
import uuid
from datetime import date
from typing import Any, Sequence

from app.db.models import ClassOccurrence
from app.engine.eligibility import CandidateGenerator
from app.engine.rules import RuleEngine, get_calendar_week_bounds
from app.schemas.planner import OptimizationPlan
from app.schemas.rules import ConstraintTypeEnum, SeverityEnum, Violation
from app.schemas.simulation import CriticIssue, CriticResult, CriticStatusEnum


class Critic:
    """
    Independent Critic that authoritatively inspects proposed plans.
    """

    def __init__(self, candidate_gen: CandidateGenerator) -> None:
        self.candidate_gen = candidate_gen
        self.db = candidate_gen.db
        self.rule_engine = RuleEngine(self.db)
        self.faculty_map = candidate_gen.faculty_map

    def critique(
        self,
        plan: OptimizationPlan,
        baseline_violations: Sequence[Violation],
        all_occurrences: Sequence[ClassOccurrence],
    ) -> CriticResult:
        """
        Critique an optimization plan and return structured CriticResult.
        """
        issues: list[CriticIssue] = []

        total_classes = len(all_occurrences)
        assigned_classes = [a for a in plan.assignments if a.is_covered and a.assigned_faculty_id]
        uncovered_classes = [a for a in plan.uncovered_assignments if not a.is_covered]

        # 1. Verify Claimed Statistics
        claims_match = True
        if len(assigned_classes) != plan.covered_occurrences:
            issues.append(
                CriticIssue(
                    issue_code="CRITIC-ERR-CLAIM-MISMATCH-COUNT",
                    severity=SeverityEnum.error,
                    message=f"Claimed covered count ({plan.covered_occurrences}) does not match actual count ({len(assigned_classes)}).",
                    details={"claimed": plan.covered_occurrences, "actual": len(assigned_classes)},
                )
            )
            claims_match = False

        expected_pct = round((len(assigned_classes) / max(total_classes, 1)) * 100.0, 1)
        if abs(plan.coverage_percentage - expected_pct) > 0.1:
            issues.append(
                CriticIssue(
                    issue_code="CRITIC-ERR-CLAIM-MISMATCH-PCT",
                    severity=SeverityEnum.error,
                    message=f"Claimed coverage percentage ({plan.coverage_percentage}%) does not match computed ({expected_pct}%).",
                    details={"claimed": plan.coverage_percentage, "computed": expected_pct},
                )
            )
            claims_match = False

        if claims_match:
            issues.append(
                CriticIssue(
                    issue_code="CRITIC-INFO-CLAIMS-VERIFIED",
                    severity=SeverityEnum.info,
                    message="Claimed coverage counts and percentages verified against assignment list.",
                )
            )

        # 2. Check Candidate Entity Integrity
        for a in assigned_classes:
            fid = a.assigned_faculty_id
            if not fid or fid not in self.faculty_map:
                issues.append(
                    CriticIssue(
                        issue_code="CRITIC-ERR-INVALID-FACULTY",
                        severity=SeverityEnum.error,
                        message=f"Assigned faculty {fid} does not exist in active database records.",
                        details={"faculty_id": str(fid), "occurrence_id": str(a.occurrence_id)},
                    )
                )
            else:
                fac = self.faculty_map[fid]
                if not fac.is_active:
                    issues.append(
                        CriticIssue(
                            issue_code="CRITIC-ERR-INACTIVE-FACULTY",
                            severity=SeverityEnum.error,
                            message=f"Assigned faculty {fac.name} is marked inactive.",
                            details={"faculty_id": str(fid)},
                        )
                    )

        # 3. Check for Overlapping Assignments in Proposed Plan
        # Group by (faculty_id, date, period_id)
        assigned_slots: dict[tuple[uuid.UUID, date, uuid.UUID], list[uuid.UUID]] = collections.defaultdict(list)
        for a in assigned_classes:
            assigned_slots[(a.assigned_faculty_id, a.occurrence_date, a.period_id)].append(a.occurrence_id)

        for (fid, occ_date, pid), occ_list in assigned_slots.items():
            if len(occ_list) > 1:
                fac_name = self.faculty_map.get(fid).name if fid in self.faculty_map else str(fid)
                issues.append(
                    CriticIssue(
                        issue_code="CRITIC-ERR-PROPOSED-OVERLAP",
                        severity=SeverityEnum.error,
                        message=f"Faculty {fac_name} is double-booked across {len(occ_list)} proposed classes on {occ_date}.",
                        details={"faculty_id": str(fid), "occurrence_ids": [str(i) for i in occ_list]},
                    )
                )

        # Also check collision against existing non-replaced schedule
        for a in assigned_classes:
            fid = a.assigned_faculty_id
            if (fid, a.occurrence_date, a.period_id) in self.candidate_gen.busy_faculty_slots:
                # Busy in existing schedule
                fac_name = self.faculty_map.get(fid).name if fid in self.faculty_map else str(fid)
                issues.append(
                    CriticIssue(
                        issue_code="CRITIC-ERR-EXISTING-SCHEDULE-COLLISION",
                        severity=SeverityEnum.error,
                        message=f"Faculty {fac_name} already teaches a regular class in period {a.period_label} on {a.occurrence_date}.",
                        details={"faculty_id": str(fid), "occurrence_id": str(a.occurrence_id)},
                    )
                )

        # 4. Check Workload Limits and High Utilization Warnings
        weekly_added_hours: dict[tuple[uuid.UUID, date], float] = collections.defaultdict(float)
        for a in assigned_classes:
            week_start, _ = get_calendar_week_bounds(a.occurrence_date)
            # Duration approximation from period times
            weekly_added_hours[(a.assigned_faculty_id, week_start)] += 1.0  # standard 1h slot

        for (fid, week_start), added_h in weekly_added_hours.items():
            fac = self.faculty_map.get(fid)
            if not fac:
                continue
            base_h = self.candidate_gen.get_assigned_hours_for_week(fid, week_start)
            total_h = base_h + added_h
            max_h = fac.weekly_max_hours
            if total_h > max_h:
                issues.append(
                    CriticIssue(
                        issue_code="CRITIC-ERR-WORKLOAD-EXCEEDED",
                        severity=SeverityEnum.error,
                        message=f"{fac.name} would be assigned {total_h}h in week of {week_start}, exceeding limit of {max_h}h.",
                        details={"assigned_hours": total_h, "weekly_max_hours": max_h},
                    )
                )
            elif total_h >= max_h * 0.90:
                issues.append(
                    CriticIssue(
                        issue_code="CRITIC-WARN-HIGH-UTILIZATION",
                        severity=SeverityEnum.warning,
                        message=f"{fac.name} is near capacity ({round((total_h/max_h)*100, 1)}% utilization: {total_h}h/{max_h}h).",
                        details={"utilization": round(total_h / max_h, 3)},
                    )
                )

        # 5. Independent State Diffing via RuleEngine (HC-09)
        replacement_map = {a.occurrence_id: a.assigned_faculty_id for a in assigned_classes}

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
            for occ in all_occurrences
        ]

        proposed_validation = self.rule_engine.validate_dated_occurrences(occurrences=simulated_list)
        diff = self.rule_engine.compare_states(
            baseline_violations=baseline_violations,
            proposed_violations=proposed_validation.violations,
        )

        new_hard_violations = [v for v in diff.new_violations if v.constraint_type == ConstraintTypeEnum.hard]
        if new_hard_violations:
            for v in new_hard_violations:
                issues.append(
                    CriticIssue(
                        issue_code="CRITIC-ERR-NEW-HARD-VIOLATION",
                        severity=SeverityEnum.error,
                        message=f"Proposed plan introduces new hard violation: {v.message}",
                        details={"rule_id": v.rule_id, "signature": v.signature},
                    )
                )

        resolved_count = len(diff.resolved_violations)

        # 6. Uncovered occurrences check
        if uncovered_classes:
            issues.append(
                CriticIssue(
                    issue_code="CRITIC-WARN-PARTIAL-COVERAGE",
                    severity=SeverityEnum.warning,
                    message=f"{len(uncovered_classes)} of {total_classes} affected class occurrences could not be covered.",
                    details={"uncovered_count": len(uncovered_classes)},
                )
            )

        # 7. Multi-State Status Determination
        has_errors = any(i.severity == SeverityEnum.error for i in issues)

        if has_errors or new_hard_violations:
            status = CriticStatusEnum.validation_failed
            is_approved = False
            summary = f"Critic REJECTED plan: {len(new_hard_violations)} new hard violation(s) or constraint error(s) detected."
        elif total_classes == 0 or len(assigned_classes) == 0:
            status = CriticStatusEnum.infeasible
            is_approved = False
            summary = "Critic evaluated: 0 classes covered; plan is infeasible."
        elif len(assigned_classes) < total_classes:
            status = CriticStatusEnum.feasible_partial
            is_approved = True
            summary = (
                f"Critic APPROVED with partial coverage: {len(assigned_classes)}/{total_classes} classes covered (0 new hard violations, "
                f"{resolved_count} baseline conflict(s) resolved)."
            )
        else:
            status = CriticStatusEnum.feasible_complete
            is_approved = True
            summary = (
                f"Critic APPROVED: 100% complete coverage ({len(assigned_classes)}/{total_classes} classes covered, 0 new hard violations, "
                f"{resolved_count} baseline conflict(s) resolved)."
            )

        return CriticResult(
            status=status,
            is_approved=is_approved,
            issues=issues,
            claims_verified=claims_match,
            new_hard_violations_count=len(new_hard_violations),
            resolved_violations_count=resolved_count,
            summary=summary,
        )

