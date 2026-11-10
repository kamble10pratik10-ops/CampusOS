"""
Candidate Eligibility and Rejection Generation (Milestone M3).

Evaluates faculty eligibility for affected class occurrences against hard constraints:
- HC-01: Overlapping classes in the same period on the target date.
- HC-03: Faculty on approved leave on the target date.
- HC-06: Course required expertise prerequisites.
- HC-07: Weekly workload capacity caps.
- HC-08: Active status.

Collects structured rejection reasons and computes soft preference scores for eligible candidates.
"""
from __future__ import annotations

import collections
import uuid
from datetime import date, timedelta
from typing import Any, Sequence

from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    ClassOccurrence,
    Course,
    Department,
    ExpertiseLevelEnum,
    Faculty,
    FacultyExpertise,
    FacultyLeave,
    Period,
    Section,
    TimetableEntry,
)
from app.engine.rules import RuleEngine, get_calendar_week_bounds
from app.schemas.planner import (
    CandidateEligibility,
    CandidateRejection,
    OccurrenceEligibility,
)


class CandidateGenerator:
    """
    Evaluates candidate faculty eligibility for affected class occurrences.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.rule_engine = RuleEngine(db)
        self._load_cache()

    def _load_cache(self) -> None:
        """Pre-load and index reference data for fast repeated eligibility queries."""
        # 1. Faculty map
        self.all_faculty: list[Faculty] = (
            self.db.query(Faculty)
            .options(joinedload(Faculty.department))
            .filter(Faculty.is_active.is_(True))
            .all()
        )
        self.faculty_map: dict[uuid.UUID, Faculty] = {f.id: f for f in self.all_faculty}

        # 2. Expertise map: faculty_id -> {tag: level}
        self.expertise_map: dict[uuid.UUID, dict[str, ExpertiseLevelEnum]] = collections.defaultdict(dict)
        for exp in self.db.query(FacultyExpertise).all():
            self.expertise_map[exp.faculty_id][exp.course_tag] = exp.level

        # 3. Leaves: faculty_id -> list[FacultyLeave]
        self.leaves_by_faculty: dict[uuid.UUID, list[FacultyLeave]] = collections.defaultdict(list)
        for lv in self.db.query(FacultyLeave).all():
            self.leaves_by_faculty[lv.faculty_id].append(lv)

        # 4. Teaching history (which faculty teaches which course/section in template)
        self.teaches_course: set[tuple[uuid.UUID, uuid.UUID]] = set()  # (faculty_id, course_id)
        self.teaches_section: set[tuple[uuid.UUID, uuid.UUID]] = set()  # (faculty_id, section_id)
        for entry in self.db.query(TimetableEntry).all():
            self.teaches_course.add((entry.faculty_id, entry.course_id))
            self.teaches_section.add((entry.faculty_id, entry.section_id))

        # 5. Pre-load active class occurrences for fast O(1) busy check and weekly hours
        self.busy_faculty_slots: set[tuple[uuid.UUID, date, uuid.UUID]] = set()
        self.weekly_hours_cache: dict[tuple[uuid.UUID, date], float] = collections.defaultdict(float)

        all_occs = (
            self.db.query(ClassOccurrence)
            .options(
                joinedload(ClassOccurrence.timetable_entry).joinedload(TimetableEntry.period),
            )
            .filter(ClassOccurrence.status != "cancelled")
            .all()
        )
        for o in all_occs:
            fid = o.effective_faculty_id
            if not fid:
                continue
            pid = o.timetable_entry.period_id if o.timetable_entry else None
            if pid:
                self.busy_faculty_slots.add((fid, o.occurrence_date, pid))

            week_start, _ = get_calendar_week_bounds(o.occurrence_date)
            dur = o.timetable_entry.period.duration_hours if o.timetable_entry and o.timetable_entry.period else 1.0
            self.weekly_hours_cache[(fid, week_start)] += dur

    def get_assigned_hours_for_week(self, faculty_id: uuid.UUID, week_date: date) -> float:
        """Calculate total hours already assigned to faculty in target calendar week."""
        week_start, _ = get_calendar_week_bounds(week_date)
        return round(self.weekly_hours_cache.get((faculty_id, week_start), 0.0), 2)

    def is_faculty_busy_at(self, faculty_id: uuid.UUID, occ_date: date, period_id: uuid.UUID) -> bool:
        """Check if faculty already has an active class on occ_date in period_id."""
        return (faculty_id, occ_date, period_id) in self.busy_faculty_slots

    def evaluate_candidate(
        self,
        faculty: Faculty,
        occurrence: ClassOccurrence,
        weights: dict[str, float] | None = None,
    ) -> CandidateEligibility:
        """
        Evaluate a single faculty member for a specific class occurrence.
        Checks all hard constraints and computes soft scores if eligible.
        """
        entry = occurrence.timetable_entry
        course = entry.course
        section = entry.section
        period = entry.period
        occ_date = occurrence.occurrence_date

        rejections: list[CandidateRejection] = []

        # 1. HC-08: Active Status
        if not faculty.is_active:
            rejections.append(
                CandidateRejection(
                    faculty_id=faculty.id,
                    faculty_name=faculty.name,
                    rule_id="HC-08",
                    reason="Faculty member is inactive",
                )
            )

        # 2. HC-03: Faculty on Leave on occ_date
        for lv in self.leaves_by_faculty.get(faculty.id, []):
            if lv.covers_date(occ_date):
                rejections.append(
                    CandidateRejection(
                        faculty_id=faculty.id,
                        faculty_name=faculty.name,
                        rule_id="HC-03",
                        reason=f"On approved leave from {lv.start_date} to {lv.end_date} ({lv.reason or 'Unspecified'})",
                        details={"leave_id": str(lv.id), "start": str(lv.start_date), "end": str(lv.end_date)},
                    )
                )
                break

        # 3. HC-01: Time Collision (already busy in same period on same date)
        if self.is_faculty_busy_at(faculty.id, occ_date, period.id):
            rejections.append(
                CandidateRejection(
                    faculty_id=faculty.id,
                    faculty_name=faculty.name,
                    rule_id="HC-01",
                    reason=f"Already assigned to a class in period {period.label} on {occ_date}",
                    details={"period_label": period.label, "date": str(occ_date)},
                )
            )

        # 4. HC-06: Course Required Expertise Tag
        if course.required_expertise_tag:
            fac_tags = self.expertise_map.get(faculty.id, {})
            if course.required_expertise_tag not in fac_tags:
                rejections.append(
                    CandidateRejection(
                        faculty_id=faculty.id,
                        faculty_name=faculty.name,
                        rule_id="HC-06",
                        reason=f"Lacks required expertise tag '{course.required_expertise_tag}' for {course.code}",
                        details={"required_tag": course.required_expertise_tag, "faculty_tags": list(fac_tags.keys())},
                    )
                )

        # 5. HC-07: Workload Limits
        assigned_h = self.get_assigned_hours_for_week(faculty.id, occ_date)
        duration = period.duration_hours if period else 1.0
        if assigned_h + duration > faculty.weekly_max_hours:
            rejections.append(
                CandidateRejection(
                    faculty_id=faculty.id,
                    faculty_name=faculty.name,
                    rule_id="HC-07",
                    reason=(
                        f"Assigning class ({duration}h) would exceed weekly cap of {faculty.weekly_max_hours}h "
                        f"(currently assigned: {assigned_h}h)"
                    ),
                    details={
                        "current_hours": assigned_h,
                        "duration": duration,
                        "weekly_max_hours": faculty.weekly_max_hours,
                    },
                )
            )

        is_eligible = len(rejections) == 0
        soft_scores: dict[str, float] = {}
        total_soft = 0.0

        if is_eligible:
            # Soft preferences evaluation
            fac_tags = self.expertise_map.get(faculty.id, {})
            exp_level = fac_tags.get(course.required_expertise_tag) if course.required_expertise_tag else None
            continuity = (faculty.id, course.id) in self.teaches_course or (faculty.id, section.id) in self.teaches_section

            pref_results = self.rule_engine.evaluate_soft_preferences(
                candidate_faculty=faculty,
                course=course,
                section=section,
                assigned_hours_this_week=assigned_h,
                already_teaches_course_or_section=continuity,
                faculty_expertise_level=exp_level,
                weights=weights,
            )
            for pr in pref_results:
                soft_scores[pr.preference_id] = pr.score
                total_soft += pr.weighted_score
            total_soft = round(total_soft, 4)

        dept_code = faculty.department.code if faculty.department else "N/A"

        return CandidateEligibility(
            faculty_id=faculty.id,
            faculty_name=faculty.name,
            employee_code=faculty.employee_code,
            department_code=dept_code,
            is_eligible=is_eligible,
            rejection_reasons=rejections,
            soft_scores=soft_scores,
            total_soft_score=total_soft,
        )

    def get_occurrence_eligibility(
        self,
        occurrence: ClassOccurrence,
        weights: dict[str, float] | None = None,
    ) -> OccurrenceEligibility:
        """Analyze complete candidate pool for a single occurrence."""
        entry = occurrence.timetable_entry
        course = entry.course
        section = entry.section
        period = entry.period

        eligible: list[CandidateEligibility] = []
        ineligible: list[CandidateEligibility] = []

        for f in self.all_faculty:
            # Do not consider the faculty who is already scheduled and needs replacement
            if f.id == entry.faculty_id:
                continue

            cand = self.evaluate_candidate(f, occurrence, weights=weights)
            if cand.is_eligible:
                eligible.append(cand)
            else:
                ineligible.append(cand)

        # Sort eligible candidates descending by total_soft_score
        eligible.sort(key=lambda c: c.total_soft_score, reverse=True)

        return OccurrenceEligibility(
            occurrence_id=occurrence.id,
            occurrence_date=occurrence.occurrence_date,
            period_id=period.id,
            period_label=period.label,
            course_code=course.code,
            course_name=course.name,
            section_name=section.name,
            total_candidates_evaluated=len(self.all_faculty) - 1,
            eligible_count=len(eligible),
            eligible_candidates=eligible,
            ineligible_candidates=ineligible,
        )
