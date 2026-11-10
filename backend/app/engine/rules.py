"""
Deterministic Rule Engine for Campus OS (Milestone M2).

Implements authoritative hard constraint checks (HC-01 to HC-10) and
soft preference evaluations (SP-01 to SP-04) as specified in SPEC.md Section 6.

Hard constraints:
    HC-01: Faculty cannot be assigned to overlapping classes.
    HC-02: Room cannot host overlapping classes.
    HC-03: Faculty cannot be assigned during applicable leave.
    HC-04: Room capacity must satisfy class enrollment requirements.
    HC-05: Lab sessions must use suitable rooms (is_lab == True).
    HC-06: Faculty expertise requirements must be respected.
    HC-07: Faculty workload must not exceed configured weekly_max_hours.
    HC-08: Invalid references, dates, assignments, and entity IDs must be rejected.
    HC-09: A proposed plan must not introduce new hard violations.
    HC-10: A simulation must not modify operational timetable records.

Soft preferences:
    SP-01: Subject expertise level (primary > secondary > none).
    SP-02: Workload balance (prefers faculty with lower current utilization).
    SP-03: Teaching continuity (prefers faculty already teaching course/section).
    SP-04: Same-department preference (prefers faculty from course department).
"""
from __future__ import annotations

import collections
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import (
    ClassOccurrence,
    Course,
    Department,
    ExpertiseLevelEnum,
    Faculty,
    FacultyExpertise,
    FacultyLeave,
    Period,
    Room,
    Section,
    TimetableEntry,
)
from app.schemas.rules import (
    ComparisonResult,
    ConstraintTypeEnum,
    EvidenceRef,
    RuleValidationResult,
    SeverityEnum,
    SoftPreferenceResult,
    Violation,
)


# ── Helper functions ───────────────────────────────────────────────────────


def get_calendar_week_bounds(target_date: date) -> tuple[date, date]:
    """Return Monday and Sunday of the calendar week containing target_date."""
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


# ── Rule Engine Class ──────────────────────────────────────────────────────


class RuleEngine:
    """
    Central deterministic rule engine.

    Provides pure validation against both database-backed state and in-memory
    simulated occurrences without mutating operational records.
    """

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    # ──────────────────────────────────────────────────────────────────────────
    # HC-01: Overlapping Faculty Assignments
    # ──────────────────────────────────────────────────────────────────────────

    def check_hc01_faculty_overlap(
        self,
        occurrences: Sequence[Any],
    ) -> list[Violation]:
        """
        HC-01: A faculty member cannot be assigned to overlapping classes.

        Accepts either ClassOccurrence objects, TimetableEntry objects, or dicts
        having faculty_id, period_id, and optionally occurrence_date.
        """
        violations: list[Violation] = []
        # Group by (faculty_id, date, period_id) or (faculty_id, period_id)
        grouped: dict[tuple, list[Any]] = collections.defaultdict(list)

        for occ in occurrences:
            fid = getattr(occ, "effective_faculty_id", None) or getattr(occ, "faculty_id", None)
            pid = getattr(occ, "period_id", None)
            if pid is None and hasattr(occ, "timetable_entry") and occ.timetable_entry:
                pid = occ.timetable_entry.period_id

            if fid is None or pid is None:
                continue

            dt = getattr(occ, "occurrence_date", None)
            key = (fid, dt, pid) if dt is not None else (fid, pid)
            grouped[key].append(occ)

        for key, group in grouped.items():
            if len(group) > 1:
                fid = key[0]
                affected_ids: list[uuid.UUID] = []
                evidence: list[EvidenceRef] = [
                    EvidenceRef(
                        ref_type="faculty",
                        ref_id=fid,
                        description=f"Faculty member assigned to {len(group)} overlapping classes"
                    )
                ]

                details: dict[str, Any] = {
                    "faculty_id": str(fid),
                    "conflicting_count": len(group),
                }

                if len(key) == 3:
                    details["occurrence_date"] = str(key[1])
                    details["period_id"] = str(key[2])
                else:
                    details["period_id"] = str(key[1])

                for item in group:
                    item_id = getattr(item, "id", None)
                    if isinstance(item_id, uuid.UUID):
                        affected_ids.append(item_id)
                        evidence.append(
                            EvidenceRef(
                                ref_type="class_occurrence" if hasattr(item, "occurrence_date") else "timetable_entry",
                                ref_id=item_id,
                                description=f"Overlapping assignment: {item_id}"
                            )
                        )

                date_str = f" on {details.get('occurrence_date')}" if "occurrence_date" in details else ""
                violations.append(
                    Violation(
                        rule_id="HC-01",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=(
                            f"Faculty {fid} is double-booked across {len(group)} classes "
                            f"in period {details['period_id']}{date_str}."
                        ),
                        affected_entity_ids=[fid] + affected_ids,
                        evidence_refs=evidence,
                        details=details,
                    )
                )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # HC-02: Overlapping Room Hosting
    # ──────────────────────────────────────────────────────────────────────────

    def check_hc02_room_overlap(
        self,
        occurrences: Sequence[Any],
    ) -> list[Violation]:
        """
        HC-02: A room cannot host overlapping classes.
        """
        violations: list[Violation] = []
        grouped: dict[tuple, list[Any]] = collections.defaultdict(list)

        for occ in occurrences:
            rid = getattr(occ, "effective_room_id", None) or getattr(occ, "room_id", None)
            pid = getattr(occ, "period_id", None)
            if pid is None and hasattr(occ, "timetable_entry") and occ.timetable_entry:
                pid = occ.timetable_entry.period_id

            if rid is None or pid is None:
                continue

            dt = getattr(occ, "occurrence_date", None)
            key = (rid, dt, pid) if dt is not None else (rid, pid)
            grouped[key].append(occ)

        for key, group in grouped.items():
            if len(group) > 1:
                rid = key[0]
                affected_ids: list[uuid.UUID] = []
                evidence: list[EvidenceRef] = [
                    EvidenceRef(
                        ref_type="room",
                        ref_id=rid,
                        description=f"Room hosting {len(group)} overlapping classes"
                    )
                ]

                details: dict[str, Any] = {
                    "room_id": str(rid),
                    "conflicting_count": len(group),
                }

                if len(key) == 3:
                    details["occurrence_date"] = str(key[1])
                    details["period_id"] = str(key[2])
                else:
                    details["period_id"] = str(key[1])

                for item in group:
                    item_id = getattr(item, "id", None)
                    if isinstance(item_id, uuid.UUID):
                        affected_ids.append(item_id)
                        evidence.append(
                            EvidenceRef(
                                ref_type="class_occurrence" if hasattr(item, "occurrence_date") else "timetable_entry",
                                ref_id=item_id,
                                description=f"Overlapping room assignment: {item_id}"
                            )
                        )

                date_str = f" on {details.get('occurrence_date')}" if "occurrence_date" in details else ""
                violations.append(
                    Violation(
                        rule_id="HC-02",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=(
                            f"Room {rid} hosts {len(group)} overlapping classes "
                            f"in period {details['period_id']}{date_str}."
                        ),
                        affected_entity_ids=[rid] + affected_ids,
                        evidence_refs=evidence,
                        details=details,
                    )
                )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # HC-03: Faculty on Applicable Leave
    # ──────────────────────────────────────────────────────────────────────────

    def check_hc03_faculty_leave(
        self,
        occurrences: Sequence[Any],
        leaves: Sequence[FacultyLeave] | None = None,
    ) -> list[Violation]:
        """
        HC-03: A faculty member cannot be assigned during applicable leave.
        Inclusive boundary: start_date <= occurrence_date <= end_date.
        """
        violations: list[Violation] = []
        if not occurrences:
            return violations

        # If leaves not provided, query DB
        if leaves is None and self.db is not None:
            leaves = self.db.query(FacultyLeave).all()
        elif leaves is None:
            leaves = []

        # Index leaves by faculty_id
        leave_by_faculty: dict[uuid.UUID, list[FacultyLeave]] = collections.defaultdict(list)
        for lv in leaves:
            leave_by_faculty[lv.faculty_id].append(lv)

        for occ in occurrences:
            occ_date = getattr(occ, "occurrence_date", None)
            if not occ_date:
                continue

            fid = getattr(occ, "effective_faculty_id", None) or getattr(occ, "faculty_id", None)
            if not fid or fid not in leave_by_faculty:
                continue

            for lv in leave_by_faculty[fid]:
                if lv.covers_date(occ_date):
                    occ_id = getattr(occ, "id", None)
                    affected_ids = [fid]
                    evidence = [
                        EvidenceRef(
                            ref_type="faculty",
                            ref_id=fid,
                            description=f"Faculty member assigned while on leave"
                        ),
                        EvidenceRef(
                            ref_type="leave",
                            ref_id=lv.id,
                            description=f"Leave record {lv.start_date} to {lv.end_date} (Reason: {lv.reason or 'Unspecified'})"
                        ),
                    ]

                    if isinstance(occ_id, uuid.UUID):
                        affected_ids.append(occ_id)
                        evidence.append(
                            EvidenceRef(
                                ref_type="class_occurrence",
                                ref_id=occ_id,
                                description=f"Class occurrence on {occ_date}"
                            )
                        )

                    violations.append(
                        Violation(
                            rule_id="HC-03",
                            constraint_type=ConstraintTypeEnum.hard,
                            severity=SeverityEnum.error,
                            message=(
                                f"Faculty {fid} is assigned to class on {occ_date} "
                                f"during approved leave from {lv.start_date} to {lv.end_date}."
                            ),
                            affected_entity_ids=affected_ids,
                            evidence_refs=evidence,
                            details={
                                "faculty_id": str(fid),
                                "occurrence_date": str(occ_date),
                                "leave_id": str(lv.id),
                                "leave_start": str(lv.start_date),
                                "leave_end": str(lv.end_date),
                                "leave_reason": lv.reason,
                            },
                        )
                    )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # HC-04: Room Capacity vs Section Enrollment
    # ──────────────────────────────────────────────────────────────────────────

    def check_hc04_room_capacity(
        self,
        assignments: Sequence[Any],
        rooms_map: dict[uuid.UUID, Room] | None = None,
        sections_map: dict[uuid.UUID, Section] | None = None,
    ) -> list[Violation]:
        """
        HC-04: Room capacity must satisfy class enrollment requirements.
        """
        violations: list[Violation] = []
        if not assignments:
            return violations

        if (rooms_map is None or sections_map is None) and self.db is not None:
            if rooms_map is None:
                rooms_map = {r.id: r for r in self.db.query(Room).all()}
            if sections_map is None:
                sections_map = {s.id: s for s in self.db.query(Section).all()}
        else:
            rooms_map = rooms_map or {}
            sections_map = sections_map or {}

        for item in assignments:
            rid = getattr(item, "effective_room_id", None) or getattr(item, "room_id", None)
            sid = getattr(item, "section_id", None)
            if sid is None and hasattr(item, "timetable_entry") and item.timetable_entry:
                sid = item.timetable_entry.section_id

            if not rid or not sid:
                continue

            room = rooms_map.get(rid)
            section = sections_map.get(sid)
            if not room or not section:
                continue

            if section.enrollment > room.capacity:
                item_id = getattr(item, "id", None)
                affected_ids = [room.id, section.id]
                evidence = [
                    EvidenceRef(
                        ref_type="room",
                        ref_id=room.id,
                        description=f"Room {room.name} has capacity {room.capacity}"
                    ),
                    EvidenceRef(
                        ref_type="section",
                        ref_id=section.id,
                        description=f"Section {section.name} has enrollment {section.enrollment}"
                    ),
                ]
                if isinstance(item_id, uuid.UUID):
                    affected_ids.append(item_id)
                    evidence.append(
                        EvidenceRef(
                            ref_type="assignment",
                            ref_id=item_id,
                            description=f"Class assignment ID {item_id}"
                        )
                    )

                violations.append(
                    Violation(
                        rule_id="HC-04",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=(
                            f"Room {room.name} capacity ({room.capacity}) is below "
                            f"section {section.name} enrollment ({section.enrollment})."
                        ),
                        affected_entity_ids=affected_ids,
                        evidence_refs=evidence,
                        details={
                            "room_id": str(room.id),
                            "room_name": room.name,
                            "room_capacity": room.capacity,
                            "section_id": str(section.id),
                            "section_name": section.name,
                            "section_enrollment": section.enrollment,
                            "deficit": section.enrollment - room.capacity,
                        },
                    )
                )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # HC-05: Lab Sessions in Suitable Rooms
    # ──────────────────────────────────────────────────────────────────────────

    def check_hc05_lab_suitability(
        self,
        assignments: Sequence[Any],
        rooms_map: dict[uuid.UUID, Room] | None = None,
        courses_map: dict[uuid.UUID, Course] | None = None,
    ) -> list[Violation]:
        """
        HC-05: Lab sessions must use suitable rooms (room.is_lab == True).
        """
        violations: list[Violation] = []
        if not assignments:
            return violations

        if (rooms_map is None or courses_map is None) and self.db is not None:
            if rooms_map is None:
                rooms_map = {r.id: r for r in self.db.query(Room).all()}
            if courses_map is None:
                courses_map = {c.id: c for c in self.db.query(Course).all()}
        else:
            rooms_map = rooms_map or {}
            courses_map = courses_map or {}

        for item in assignments:
            rid = getattr(item, "effective_room_id", None) or getattr(item, "room_id", None)
            cid = getattr(item, "course_id", None)
            if cid is None and hasattr(item, "timetable_entry") and item.timetable_entry:
                cid = item.timetable_entry.course_id

            if not rid or not cid:
                continue

            room = rooms_map.get(rid)
            course = courses_map.get(cid)
            if not room or not course:
                continue

            if course.requires_lab and not room.is_lab:
                item_id = getattr(item, "id", None)
                affected_ids = [room.id, course.id]
                evidence = [
                    EvidenceRef(
                        ref_type="course",
                        ref_id=course.id,
                        description=f"Course {course.code} ({course.name}) requires laboratory facilities"
                    ),
                    EvidenceRef(
                        ref_type="room",
                        ref_id=room.id,
                        description=f"Room {room.name} is a regular classroom (is_lab=False)"
                    ),
                ]
                if isinstance(item_id, uuid.UUID):
                    affected_ids.append(item_id)
                    evidence.append(
                        EvidenceRef(
                            ref_type="assignment",
                            ref_id=item_id,
                            description=f"Assignment ID {item_id}"
                        )
                    )

                violations.append(
                    Violation(
                        rule_id="HC-05",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=(
                            f"Course {course.code} requires a lab, but Room {room.name} "
                            f"is not a designated laboratory."
                        ),
                        affected_entity_ids=affected_ids,
                        evidence_refs=evidence,
                        details={
                            "course_id": str(course.id),
                            "course_code": course.code,
                            "requires_lab": True,
                            "room_id": str(room.id),
                            "room_name": room.name,
                            "room_is_lab": room.is_lab,
                        },
                    )
                )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # HC-06: Faculty Expertise Requirements
    # ──────────────────────────────────────────────────────────────────────────

    def check_hc06_faculty_expertise(
        self,
        assignments: Sequence[Any],
        faculty_expertise_map: dict[uuid.UUID, set[str]] | None = None,
        courses_map: dict[uuid.UUID, Course] | None = None,
        faculty_map: dict[uuid.UUID, Faculty] | None = None,
    ) -> list[Violation]:
        """
        HC-06: Faculty expertise requirements must be respected where course has explicit requirement.
        """
        violations: list[Violation] = []
        if not assignments:
            return violations

        if (faculty_expertise_map is None or courses_map is None or faculty_map is None) and self.db is not None:
            if courses_map is None:
                courses_map = {c.id: c for c in self.db.query(Course).all()}
            if faculty_map is None:
                faculty_map = {f.id: f for f in self.db.query(Faculty).all()}
            if faculty_expertise_map is None:
                faculty_expertise_map = collections.defaultdict(set)
                for exp in self.db.query(FacultyExpertise).all():
                    faculty_expertise_map[exp.faculty_id].add(exp.course_tag)
        else:
            faculty_expertise_map = faculty_expertise_map or {}
            courses_map = courses_map or {}
            faculty_map = faculty_map or {}

        for item in assignments:
            fid = getattr(item, "effective_faculty_id", None) or getattr(item, "faculty_id", None)
            cid = getattr(item, "course_id", None)
            if cid is None and hasattr(item, "timetable_entry") and item.timetable_entry:
                cid = item.timetable_entry.course_id

            if not fid or not cid:
                continue

            course = courses_map.get(cid)
            if not course or not course.required_expertise_tag:
                continue

            faculty = faculty_map.get(fid)
            expertise_tags = faculty_expertise_map.get(fid, set())

            if course.required_expertise_tag not in expertise_tags:
                item_id = getattr(item, "id", None)
                fac_name = faculty.name if faculty else f"Faculty {fid}"
                affected_ids = [fid, course.id]
                evidence = [
                    EvidenceRef(
                        ref_type="course",
                        ref_id=course.id,
                        description=f"Course {course.code} requires expertise tag '{course.required_expertise_tag}'"
                    ),
                    EvidenceRef(
                        ref_type="faculty",
                        ref_id=fid,
                        description=f"{fac_name} expertise tags: {sorted(expertise_tags) or 'None'}"
                    ),
                ]
                if isinstance(item_id, uuid.UUID):
                    affected_ids.append(item_id)
                    evidence.append(
                        EvidenceRef(
                            ref_type="assignment",
                            ref_id=item_id,
                            description=f"Assignment ID {item_id}"
                        )
                    )

                violations.append(
                    Violation(
                        rule_id="HC-06",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=(
                            f"{fac_name} lacks required expertise '{course.required_expertise_tag}' "
                            f"for course {course.code} ({course.name})."
                        ),
                        affected_entity_ids=affected_ids,
                        evidence_refs=evidence,
                        details={
                            "faculty_id": str(fid),
                            "faculty_name": fac_name,
                            "course_id": str(course.id),
                            "course_code": course.code,
                            "required_tag": course.required_expertise_tag,
                            "faculty_tags": sorted(list(expertise_tags)),
                        },
                    )
                )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # HC-07: Faculty Workload Limits
    # ──────────────────────────────────────────────────────────────────────────

    def check_hc07_workload_limits(
        self,
        occurrences: Sequence[Any],
        faculty_map: dict[uuid.UUID, Faculty] | None = None,
        periods_map: dict[uuid.UUID, Period] | None = None,
        target_week_date: date | None = None,
    ) -> list[Violation]:
        """
        HC-07: Faculty workload must not exceed configured weekly_max_hours.
        Calculated as the sum of period durations across the Mon-Sun week.
        """
        violations: list[Violation] = []
        if not occurrences:
            return violations

        if (faculty_map is None or periods_map is None) and self.db is not None:
            if faculty_map is None:
                faculty_map = {f.id: f for f in self.db.query(Faculty).all()}
            if periods_map is None:
                periods_map = {p.id: p for p in self.db.query(Period).all()}
        else:
            faculty_map = faculty_map or {}
            periods_map = periods_map or {}

        # Group occurrences by (faculty_id, week_start_date)
        faculty_week_hours: dict[tuple[uuid.UUID, date], float] = collections.defaultdict(float)
        faculty_week_occs: dict[tuple[uuid.UUID, date], list[Any]] = collections.defaultdict(list)

        for occ in occurrences:
            dt = getattr(occ, "occurrence_date", None)
            if not dt and target_week_date:
                dt = target_week_date
            elif not dt:
                # If no occurrence date, assume single weekly template context
                dt = date(2026, 10, 26)

            mon, _ = get_calendar_week_bounds(dt)
            fid = getattr(occ, "effective_faculty_id", None) or getattr(occ, "faculty_id", None)
            pid = getattr(occ, "period_id", None)
            if pid is None and hasattr(occ, "timetable_entry") and occ.timetable_entry:
                pid = occ.timetable_entry.period_id

            if not fid or not pid:
                continue

            period = periods_map.get(pid)
            duration = period.duration_hours if period else 1.0

            key = (fid, mon)
            faculty_week_hours[key] += duration
            faculty_week_occs[key].append(occ)

        for (fid, week_start), total_hours in faculty_week_hours.items():
            faculty = faculty_map.get(fid)
            if not faculty:
                continue

            max_h = faculty.weekly_max_hours
            if total_hours > max_h:
                week_end = week_start + timedelta(days=6)
                affected_occs = faculty_week_occs[(fid, week_start)]
                occ_ids = [getattr(o, "id") for o in affected_occs if getattr(o, "id", None)]

                evidence = [
                    EvidenceRef(
                        ref_type="faculty",
                        ref_id=fid,
                        description=f"{faculty.name} max capacity is {max_h}h/week"
                    ),
                ]
                for o in affected_occs[:5]:  # include up to 5 occurrence refs
                    oid = getattr(o, "id", None)
                    if isinstance(oid, uuid.UUID):
                        evidence.append(
                            EvidenceRef(
                                ref_type="class_occurrence",
                                ref_id=oid,
                                description=f"Class on {getattr(o, 'occurrence_date', 'template')}"
                            )
                        )

                violations.append(
                    Violation(
                        rule_id="HC-07",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=(
                            f"{faculty.name} is assigned {round(total_hours, 2)} hours "
                            f"for week of {week_start}, exceeding limit of {max_h} hours."
                        ),
                        affected_entity_ids=[fid] + [i for i in occ_ids if isinstance(i, uuid.UUID)],
                        evidence_refs=evidence,
                        details={
                            "faculty_id": str(fid),
                            "faculty_name": faculty.name,
                            "week_start": str(week_start),
                            "week_end": str(week_end),
                            "assigned_hours": round(total_hours, 2),
                            "weekly_max_hours": max_h,
                            "overload_hours": round(total_hours - max_h, 2),
                        },
                    )
                )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # HC-08: Invalid References and Data Integrity
    # ──────────────────────────────────────────────────────────────────────────

    def check_hc08_data_integrity(
        self,
        assignments: Sequence[Any],
        known_faculty_ids: set[uuid.UUID] | None = None,
        known_room_ids: set[uuid.UUID] | None = None,
        known_course_ids: set[uuid.UUID] | None = None,
        known_section_ids: set[uuid.UUID] | None = None,
        known_periods_map: dict[uuid.UUID, Period] | None = None,
    ) -> list[Violation]:
        """
        HC-08: Invalid references, dates, assignments, and entity IDs must be rejected.
        Checks:
        - Non-existent entity references
        - Inactive faculty or rooms
        - Occurrence date weekday mismatching period weekday
        - Invalid period times (end_time <= start_time)
        """
        violations: list[Violation] = []
        if not assignments:
            return violations

        if self.db is not None and None in (
            known_faculty_ids,
            known_room_ids,
            known_course_ids,
            known_section_ids,
            known_periods_map,
        ):
            known_faculty_ids = {f.id for f in self.db.query(Faculty).filter(Faculty.is_active == True).all()}
            known_room_ids = {r.id for r in self.db.query(Room).filter(Room.is_active == True).all()}
            known_course_ids = {c.id for c in self.db.query(Course).all()}
            known_section_ids = {s.id for s in self.db.query(Section).all()}
            known_periods_map = {p.id: p for p in self.db.query(Period).all()}
        else:
            known_faculty_ids = known_faculty_ids or set()
            known_room_ids = known_room_ids or set()
            known_course_ids = known_course_ids or set()
            known_section_ids = known_section_ids or set()
            known_periods_map = known_periods_map or {}

        for item in assignments:
            item_id = getattr(item, "id", None)
            fid = getattr(item, "effective_faculty_id", None) or getattr(item, "faculty_id", None)
            rid = getattr(item, "effective_room_id", None) or getattr(item, "room_id", None)
            cid = getattr(item, "course_id", None)
            sid = getattr(item, "section_id", None)
            pid = getattr(item, "period_id", None)

            if hasattr(item, "timetable_entry") and item.timetable_entry:
                cid = cid or item.timetable_entry.course_id
                sid = sid or item.timetable_entry.section_id
                pid = pid or item.timetable_entry.period_id

            # 1. Non-existent / inactive faculty
            if fid and fid not in known_faculty_ids:
                violations.append(
                    Violation(
                        rule_id="HC-08",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=f"Assignment references invalid or inactive faculty ID: {fid}.",
                        affected_entity_ids=[fid],
                        evidence_refs=[EvidenceRef(ref_type="faculty", ref_id=fid, description="Unrecognized or inactive faculty ID")],
                        details={"invalid_field": "faculty_id", "value": str(fid)},
                    )
                )

            # 2. Non-existent / inactive room
            if rid and rid not in known_room_ids:
                violations.append(
                    Violation(
                        rule_id="HC-08",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=f"Assignment references invalid or inactive room ID: {rid}.",
                        affected_entity_ids=[rid],
                        evidence_refs=[EvidenceRef(ref_type="room", ref_id=rid, description="Unrecognized or inactive room ID")],
                        details={"invalid_field": "room_id", "value": str(rid)},
                    )
                )

            # 3. Non-existent course
            if cid and cid not in known_course_ids:
                violations.append(
                    Violation(
                        rule_id="HC-08",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=f"Assignment references non-existent course ID: {cid}.",
                        affected_entity_ids=[cid],
                        evidence_refs=[EvidenceRef(ref_type="course", ref_id=cid, description="Unrecognized course ID")],
                        details={"invalid_field": "course_id", "value": str(cid)},
                    )
                )

            # 4. Non-existent section
            if sid and sid not in known_section_ids:
                violations.append(
                    Violation(
                        rule_id="HC-08",
                        constraint_type=ConstraintTypeEnum.hard,
                        severity=SeverityEnum.error,
                        message=f"Assignment references non-existent section ID: {sid}.",
                        affected_entity_ids=[sid],
                        evidence_refs=[EvidenceRef(ref_type="section", ref_id=sid, description="Unrecognized section ID")],
                        details={"invalid_field": "section_id", "value": str(sid)},
                    )
                )

            # 5. Period checks
            if pid:
                period = known_periods_map.get(pid)
                if not period:
                    violations.append(
                        Violation(
                            rule_id="HC-08",
                            constraint_type=ConstraintTypeEnum.hard,
                            severity=SeverityEnum.error,
                            message=f"Assignment references non-existent period ID: {pid}.",
                            affected_entity_ids=[pid],
                            evidence_refs=[EvidenceRef(ref_type="period", ref_id=pid, description="Unrecognized period ID")],
                            details={"invalid_field": "period_id", "value": str(pid)},
                        )
                    )
                else:
                    # Check period start < end
                    if period.end_time <= period.start_time:
                        violations.append(
                            Violation(
                                rule_id="HC-08",
                                constraint_type=ConstraintTypeEnum.hard,
                                severity=SeverityEnum.error,
                                message=f"Period {pid} has invalid times: end_time ({period.end_time}) <= start_time ({period.start_time}).",
                                affected_entity_ids=[pid],
                                evidence_refs=[EvidenceRef(ref_type="period", ref_id=pid, description="Invalid period start/end times")],
                                details={"period_id": str(pid), "start_time": str(period.start_time), "end_time": str(period.end_time)},
                            )
                        )

                    # Check occurrence date weekday matches period weekday
                    occ_date = getattr(item, "occurrence_date", None)
                    if occ_date and occ_date.weekday() != period.weekday:
                        violations.append(
                            Violation(
                                rule_id="HC-08",
                                constraint_type=ConstraintTypeEnum.hard,
                                severity=SeverityEnum.error,
                                message=(
                                    f"Occurrence date {occ_date} (weekday {occ_date.weekday()}) "
                                    f"does not match period weekday {period.weekday}."
                                ),
                                affected_entity_ids=[item_id or pid],
                                evidence_refs=[
                                    EvidenceRef(ref_type="period", ref_id=pid, description=f"Period weekday is {period.weekday}"),
                                    EvidenceRef(ref_type="date", ref_id=None, description=f"Date is {occ_date} (weekday {occ_date.weekday()})"),
                                ],
                                details={
                                    "occurrence_date": str(occ_date),
                                    "date_weekday": occ_date.weekday(),
                                    "period_id": str(pid),
                                    "period_weekday": period.weekday,
                                },
                            )
                        )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # HC-09: Plan Comparison & New Hard Violations Check
    # ──────────────────────────────────────────────────────────────────────────

    def compare_states(
        self,
        baseline_violations: Sequence[Violation],
        proposed_violations: Sequence[Violation],
    ) -> ComparisonResult:
        """
        HC-09: A proposed plan must not introduce new hard violations.
        Compares baseline and proposed states using deterministic signatures.
        """
        baseline_sig_map = {v.signature: v for v in baseline_violations}
        proposed_sig_map = {v.signature: v for v in proposed_violations}

        baseline_sigs = set(baseline_sig_map.keys())
        proposed_sigs = set(proposed_sig_map.keys())

        existing_sigs = baseline_sigs & proposed_sigs
        resolved_sigs = baseline_sigs - proposed_sigs
        new_sigs = proposed_sigs - baseline_sigs

        existing_violations = [proposed_sig_map[sig] for sig in existing_sigs]
        resolved_violations = [baseline_sig_map[sig] for sig in resolved_sigs]
        new_violations = [proposed_sig_map[sig] for sig in new_sigs]
        remaining_violations = list(existing_violations)

        introduces_new_hard = any(
            v.constraint_type == ConstraintTypeEnum.hard for v in new_violations
        )

        return ComparisonResult(
            baseline_violations=list(baseline_violations),
            proposed_violations=list(proposed_violations),
            existing_violations=existing_violations,
            resolved_violations=resolved_violations,
            new_violations=new_violations,
            remaining_violations=remaining_violations,
            introduces_new_hard_violations=introduces_new_hard,
            is_valid=not introduces_new_hard,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # HC-10: Non-Mutation Verification
    # ──────────────────────────────────────────────────────────────────────────

    def verify_no_mutation(
        self,
        snapshot_counts_before: dict[str, int],
    ) -> list[Violation]:
        """
        HC-10: A simulation must not modify operational timetable records.
        Verifies that row counts / states in operational tables are unchanged.
        """
        violations: list[Violation] = []
        if self.db is None:
            return violations

        current_counts = {
            "timetable_entry": self.db.query(TimetableEntry).count(),
            "class_occurrence": self.db.query(ClassOccurrence).count(),
            "faculty": self.db.query(Faculty).count(),
            "faculty_leave": self.db.query(FacultyLeave).count(),
        }

        mutations = []
        for table, before_cnt in snapshot_counts_before.items():
            curr_cnt = current_counts.get(table, 0)
            if curr_cnt != before_cnt:
                mutations.append(f"{table}: {before_cnt} -> {curr_cnt}")

        if mutations:
            violations.append(
                Violation(
                    rule_id="HC-10",
                    constraint_type=ConstraintTypeEnum.hard,
                    severity=SeverityEnum.error,
                    message=f"Simulation mutated operational database records: {', '.join(mutations)}.",
                    affected_entity_ids=[],
                    evidence_refs=[EvidenceRef(ref_type="database", ref_id=None, description="Operational table row count mismatch")],
                    details={"mutations": mutations},
                )
            )

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # Soft Preferences: SP-01 to SP-04
    # ──────────────────────────────────────────────────────────────────────────

    def evaluate_soft_preferences(
        self,
        candidate_faculty: Faculty,
        course: Course,
        section: Section,
        assigned_hours_this_week: float,
        already_teaches_course_or_section: bool = False,
        faculty_expertise_level: ExpertiseLevelEnum | None = None,
        weights: dict[str, float] | None = None,
    ) -> list[SoftPreferenceResult]:
        """
        Evaluates soft preferences (SP-01 to SP-04) for a candidate assignment.
        Standard weights (SPEC.md Section 7):
            SP-01 (Subject expertise): 0.35
            SP-02 (Workload balance): 0.30
            SP-03 (Continuity of teaching): 0.25
            SP-04 (Same department): 0.10
        """
        w = weights or {
            "SP-01": 0.35,
            "SP-02": 0.30,
            "SP-03": 0.25,
            "SP-04": 0.10,
        }

        results: list[SoftPreferenceResult] = []

        # 1. SP-01: Subject Expertise Level
        if faculty_expertise_level == ExpertiseLevelEnum.primary:
            sp01_score = 1.0
            sp01_exp = "Primary subject matter expertise"
        elif faculty_expertise_level == ExpertiseLevelEnum.secondary:
            sp01_score = 0.7
            sp01_exp = "Secondary subject matter expertise"
        elif not course.required_expertise_tag:
            sp01_score = 0.8  # No specific expertise required for course
            sp01_exp = "Course has no specialized expertise prerequisite"
        else:
            sp01_score = 0.1
            sp01_exp = "No documented expertise in this subject"

        results.append(
            SoftPreferenceResult(
                preference_id="SP-01",
                name="Subject Expertise",
                score=sp01_score,
                weight=w["SP-01"],
                weighted_score=round(sp01_score * w["SP-01"], 4),
                details={"expertise_level": str(faculty_expertise_level)},
                explanation=sp01_exp,
            )
        )

        # 2. SP-02: Workload Balance
        max_h = max(candidate_faculty.weekly_max_hours, 1.0)
        utilization = min(assigned_hours_this_week / max_h, 1.0)
        sp02_score = round(max(0.0, 1.0 - utilization), 4)
        sp02_exp = f"Current utilization is {round(utilization * 100, 1)}% ({assigned_hours_this_week}h/{max_h}h)"

        results.append(
            SoftPreferenceResult(
                preference_id="SP-02",
                name="Workload Balance",
                score=sp02_score,
                weight=w["SP-02"],
                weighted_score=round(sp02_score * w["SP-02"], 4),
                details={
                    "assigned_hours": assigned_hours_this_week,
                    "weekly_max_hours": max_h,
                    "utilization": utilization,
                },
                explanation=sp02_exp,
            )
        )

        # 3. SP-03: Continuity of Teaching
        sp03_score = 1.0 if already_teaches_course_or_section else 0.2
        sp03_exp = "Faculty already instructs this course or section" if already_teaches_course_or_section else "New instructor for this cohort"

        results.append(
            SoftPreferenceResult(
                preference_id="SP-03",
                name="Teaching Continuity",
                score=sp03_score,
                weight=w["SP-03"],
                weighted_score=round(sp03_score * w["SP-03"], 4),
                details={"continuity": already_teaches_course_or_section},
                explanation=sp03_exp,
            )
        )

        # 4. SP-04: Same Department
        is_same_dept = candidate_faculty.department_id == course.department_id
        sp04_score = 1.0 if is_same_dept else 0.4
        sp04_exp = "Same department faculty member" if is_same_dept else "Cross-department faculty member"

        results.append(
            SoftPreferenceResult(
                preference_id="SP-04",
                name="Department Affinity",
                score=sp04_score,
                weight=w["SP-04"],
                weighted_score=round(sp04_score * w["SP-04"], 4),
                details={"same_department": is_same_dept},
                explanation=sp04_exp,
            )
        )

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Comprehensive Validation Suites
    # ──────────────────────────────────────────────────────────────────────────

    def validate_timetable_template(
        self,
        entries: Sequence[TimetableEntry] | None = None,
    ) -> RuleValidationResult:
        """
        Validate the recurring weekly timetable template against all applicable hard constraints:
        HC-01, HC-02, HC-04, HC-05, HC-06, HC-07, HC-08.
        """
        if entries is None and self.db is not None:
            entries = self.db.query(TimetableEntry).all()
        elif entries is None:
            entries = []

        all_violations: list[Violation] = []

        # HC-01: Faculty overlap
        all_violations.extend(self.check_hc01_faculty_overlap(entries))
        # HC-02: Room overlap
        all_violations.extend(self.check_hc02_room_overlap(entries))
        # HC-04: Capacity
        all_violations.extend(self.check_hc04_room_capacity(entries))
        # HC-05: Lab suitability
        all_violations.extend(self.check_hc05_lab_suitability(entries))
        # HC-06: Faculty expertise
        all_violations.extend(self.check_hc06_faculty_expertise(entries))
        # HC-07: Workload limit
        all_violations.extend(self.check_hc07_workload_limits(entries))
        # HC-08: Data integrity
        all_violations.extend(self.check_hc08_data_integrity(entries))

        by_rule: dict[str, list[Violation]] = collections.defaultdict(list)
        hard_count = 0
        soft_count = 0

        for v in all_violations:
            by_rule[v.rule_id].append(v)
            if v.constraint_type == ConstraintTypeEnum.hard:
                hard_count += 1
            else:
                soft_count += 1

        return RuleValidationResult(
            is_valid=(hard_count == 0),
            total_violations=len(all_violations),
            hard_violations_count=hard_count,
            soft_violations_count=soft_count,
            violations=all_violations,
            by_rule=dict(by_rule),
        )

    def validate_dated_occurrences(
        self,
        occurrences: Sequence[ClassOccurrence] | None = None,
        target_date: date | None = None,
        leaves: Sequence[FacultyLeave] | None = None,
    ) -> RuleValidationResult:
        """
        Validate dated class occurrences against all hard constraints including HC-03 (Faculty leave).
        """
        if occurrences is None and self.db is not None:
            q = self.db.query(ClassOccurrence)
            if target_date:
                q = q.filter(ClassOccurrence.occurrence_date == target_date)
            occurrences = q.all()
        elif occurrences is None:
            occurrences = []

        all_violations: list[Violation] = []

        # HC-01: Faculty overlap on date
        all_violations.extend(self.check_hc01_faculty_overlap(occurrences))
        # HC-02: Room overlap on date
        all_violations.extend(self.check_hc02_room_overlap(occurrences))
        # HC-03: Faculty on leave
        all_violations.extend(self.check_hc03_faculty_leave(occurrences, leaves=leaves))
        # HC-04: Capacity
        all_violations.extend(self.check_hc04_room_capacity(occurrences))
        # HC-05: Lab suitability
        all_violations.extend(self.check_hc05_lab_suitability(occurrences))
        # HC-06: Faculty expertise
        all_violations.extend(self.check_hc06_faculty_expertise(occurrences))
        # HC-07: Workload limit
        all_violations.extend(self.check_hc07_workload_limits(occurrences, target_week_date=target_date))
        # HC-08: Data integrity
        all_violations.extend(self.check_hc08_data_integrity(occurrences))

        by_rule: dict[str, list[Violation]] = collections.defaultdict(list)
        hard_count = 0
        soft_count = 0

        for v in all_violations:
            by_rule[v.rule_id].append(v)
            if v.constraint_type == ConstraintTypeEnum.hard:
                hard_count += 1
            else:
                soft_count += 1

        return RuleValidationResult(
            is_valid=(hard_count == 0),
            total_violations=len(all_violations),
            hard_violations_count=hard_count,
            soft_violations_count=soft_count,
            violations=all_violations,
            by_rule=dict(by_rule),
        )

