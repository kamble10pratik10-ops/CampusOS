"""
test_rules.py — Comprehensive tests for the Deterministic Rule Engine (Milestone M2).

Covers:
- Hard Constraints HC-01 through HC-10 (Positive and Negative unit tests)
- Soft Preferences SP-01 through SP-04
- Detection of planted seed conflicts (HC-01, HC-02, HC-04, HC-05, HC-06)
- Hero scenario leave conflict detection (HC-03)
- Non-mutation check (HC-10)
- State diffing and deterministic signatures (HC-09)
- API endpoint integration: GET /conflicts, GET /workload, and updated GET /dashboard
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
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
from app.engine.rules import RuleEngine, get_calendar_week_bounds
from app.schemas.rules import (
    ComparisonResult,
    ConstraintTypeEnum,
    EvidenceRef,
    RuleValidationResult,
    SeverityEnum,
    Violation,
)


# ── Helper Mocks / In-Memory Objects for Pure Unit Tests ───────────────────


class SimpleSlot:
    """Lightweight slot fixture for unit testing rule checks."""
    def __init__(
        self,
        id: uuid.UUID | None = None,
        faculty_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        course_id: uuid.UUID | None = None,
        section_id: uuid.UUID | None = None,
        period_id: uuid.UUID | None = None,
        occurrence_date: date | None = None,
        effective_faculty_id: uuid.UUID | None = None,
        effective_room_id: uuid.UUID | None = None,
    ):
        self.id = id or uuid.uuid4()
        self.faculty_id = faculty_id or uuid.uuid4()
        self.room_id = room_id or uuid.uuid4()
        self.course_id = course_id or uuid.uuid4()
        self.section_id = section_id or uuid.uuid4()
        self.period_id = period_id or uuid.uuid4()
        self.occurrence_date = occurrence_date
        self.effective_faculty_id = effective_faculty_id or self.faculty_id
        self.effective_room_id = effective_room_id or self.room_id


# ── HC-01: Faculty Overlap ────────────────────────────────────────────────


def test_hc01_positive_no_overlap():
    """Different faculty in same period, or same faculty in different periods -> valid."""
    engine = RuleEngine()
    f1, f2 = uuid.uuid4(), uuid.uuid4()
    p1, p2 = uuid.uuid4(), uuid.uuid4()

    slots = [
        SimpleSlot(faculty_id=f1, period_id=p1),
        SimpleSlot(faculty_id=f2, period_id=p1),  # different faculty, same period
        SimpleSlot(faculty_id=f1, period_id=p2),  # same faculty, different period
    ]
    violations = engine.check_hc01_faculty_overlap(slots)
    assert len(violations) == 0


def test_hc01_negative_double_booked_faculty():
    """Same faculty assigned to two classes in the same period -> HC-01 violation."""
    engine = RuleEngine()
    fid = uuid.uuid4()
    pid = uuid.uuid4()

    s1 = SimpleSlot(faculty_id=fid, period_id=pid)
    s2 = SimpleSlot(faculty_id=fid, period_id=pid)

    violations = engine.check_hc01_faculty_overlap([s1, s2])
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "HC-01"
    assert v.constraint_type == ConstraintTypeEnum.hard
    assert v.severity == SeverityEnum.error
    assert fid in v.affected_entity_ids
    assert s1.id in v.affected_entity_ids
    assert s2.id in v.affected_entity_ids
    assert any(e.ref_type == "faculty" and e.ref_id == fid for e in v.evidence_refs)


# ── HC-02: Room Overlap ───────────────────────────────────────────────────


def test_hc02_positive_no_overlap():
    """Different rooms in same period, or same room in different periods -> valid."""
    engine = RuleEngine()
    r1, r2 = uuid.uuid4(), uuid.uuid4()
    p1, p2 = uuid.uuid4(), uuid.uuid4()

    slots = [
        SimpleSlot(room_id=r1, period_id=p1),
        SimpleSlot(room_id=r2, period_id=p1),
        SimpleSlot(room_id=r1, period_id=p2),
    ]
    violations = engine.check_hc02_room_overlap(slots)
    assert len(violations) == 0


def test_hc02_negative_double_booked_room():
    """Same room hosting two classes in the same period -> HC-02 violation."""
    engine = RuleEngine()
    rid = uuid.uuid4()
    pid = uuid.uuid4()

    s1 = SimpleSlot(room_id=rid, period_id=pid)
    s2 = SimpleSlot(room_id=rid, period_id=pid)

    violations = engine.check_hc02_room_overlap([s1, s2])
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "HC-02"
    assert v.constraint_type == ConstraintTypeEnum.hard
    assert rid in v.affected_entity_ids
    assert s1.id in v.affected_entity_ids
    assert s2.id in v.affected_entity_ids


# ── HC-03: Faculty on Leave ───────────────────────────────────────────────


def test_hc03_positive_class_outside_leave():
    """Class before start_date or after end_date -> no violation."""
    engine = RuleEngine()
    fid = uuid.uuid4()
    leave = MagicMock(spec=FacultyLeave)
    leave.id = uuid.uuid4()
    leave.faculty_id = fid
    leave.start_date = date(2026, 11, 2)
    leave.end_date = date(2026, 11, 4)
    leave.covers_date.side_effect = lambda d: date(2026, 11, 2) <= d <= date(2026, 11, 4)

    s1 = SimpleSlot(faculty_id=fid, occurrence_date=date(2026, 11, 1))
    s2 = SimpleSlot(faculty_id=fid, occurrence_date=date(2026, 11, 5))

    violations = engine.check_hc03_faculty_leave([s1, s2], leaves=[leave])
    assert len(violations) == 0


def test_hc03_negative_class_during_leave():
    """Class on start_date, mid-date, or end_date of leave -> HC-03 violation."""
    engine = RuleEngine()
    fid = uuid.uuid4()
    leave = MagicMock(spec=FacultyLeave)
    leave.id = uuid.uuid4()
    leave.faculty_id = fid
    leave.start_date = date(2026, 11, 2)
    leave.end_date = date(2026, 11, 4)
    leave.reason = "Medical emergency"
    leave.covers_date.side_effect = lambda d: date(2026, 11, 2) <= d <= date(2026, 11, 4)

    s_start = SimpleSlot(faculty_id=fid, occurrence_date=date(2026, 11, 2))
    s_mid = SimpleSlot(faculty_id=fid, occurrence_date=date(2026, 11, 3))
    s_end = SimpleSlot(faculty_id=fid, occurrence_date=date(2026, 11, 4))

    violations = engine.check_hc03_faculty_leave([s_start, s_mid, s_end], leaves=[leave])
    assert len(violations) == 3
    for v in violations:
        assert v.rule_id == "HC-03"
        assert v.constraint_type == ConstraintTypeEnum.hard
        assert fid in v.affected_entity_ids
        assert any(e.ref_type == "leave" and e.ref_id == leave.id for e in v.evidence_refs)


# ── HC-04: Room Capacity ──────────────────────────────────────────────────


def test_hc04_positive_sufficient_capacity():
    """Room capacity >= section enrollment -> valid."""
    engine = RuleEngine()
    rid = uuid.uuid4()
    sid = uuid.uuid4()

    room = MagicMock(spec=Room)
    room.id = rid
    room.name = "Room 101"
    room.capacity = 60

    section = MagicMock(spec=Section)
    section.id = sid
    section.name = "CS-1A"
    section.enrollment = 60

    slot = SimpleSlot(room_id=rid, section_id=sid)
    violations = engine.check_hc04_room_capacity([slot], rooms_map={rid: room}, sections_map={sid: section})
    assert len(violations) == 0


def test_hc04_negative_capacity_exceeded():
    """Room capacity < section enrollment -> HC-04 violation."""
    engine = RuleEngine()
    rid = uuid.uuid4()
    sid = uuid.uuid4()

    room = MagicMock(spec=Room)
    room.id = rid
    room.name = "Room 101"
    room.capacity = 50

    section = MagicMock(spec=Section)
    section.id = sid
    section.name = "CS-1A"
    section.enrollment = 65

    slot = SimpleSlot(room_id=rid, section_id=sid)
    violations = engine.check_hc04_room_capacity([slot], rooms_map={rid: room}, sections_map={sid: section})
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "HC-04"
    assert v.details["deficit"] == 15
    assert rid in v.affected_entity_ids
    assert sid in v.affected_entity_ids


# ── HC-05: Lab Suitability ────────────────────────────────────────────────


def test_hc05_positive_lab_in_lab_room():
    """Lab course in is_lab=True room, and regular course in any room -> valid."""
    engine = RuleEngine()
    r_lab = MagicMock(spec=Room, id=uuid.uuid4(), name="Lab 1", is_lab=True)
    r_cls = MagicMock(spec=Room, id=uuid.uuid4(), name="Room 101", is_lab=False)

    c_lab = MagicMock(spec=Course, id=uuid.uuid4(), code="CS202", requires_lab=True)
    c_cls = MagicMock(spec=Course, id=uuid.uuid4(), code="CS201", requires_lab=False)

    slots = [
        SimpleSlot(room_id=r_lab.id, course_id=c_lab.id),  # lab course in lab room
        SimpleSlot(room_id=r_cls.id, course_id=c_cls.id),  # lecture in regular classroom
        SimpleSlot(room_id=r_lab.id, course_id=c_cls.id),  # lecture in lab room (allowed)
    ]
    rooms_map = {r_lab.id: r_lab, r_cls.id: r_cls}
    courses_map = {c_lab.id: c_lab, c_cls.id: c_cls}

    violations = engine.check_hc05_lab_suitability(slots, rooms_map=rooms_map, courses_map=courses_map)
    assert len(violations) == 0


def test_hc05_negative_lab_in_classroom():
    """Lab course assigned to is_lab=False room -> HC-05 violation."""
    engine = RuleEngine()
    room = MagicMock(spec=Room, id=uuid.uuid4(), name="Room 101", is_lab=False)
    course = MagicMock(spec=Course, id=uuid.uuid4(), code="CS402", name="Networks Lab", requires_lab=True)

    slot = SimpleSlot(room_id=room.id, course_id=course.id)
    violations = engine.check_hc05_lab_suitability(
        [slot], rooms_map={room.id: room}, courses_map={course.id: course}
    )
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "HC-05"
    assert room.id in v.affected_entity_ids
    assert course.id in v.affected_entity_ids
    assert v.details["room_is_lab"] is False


# ── HC-06: Faculty Expertise ──────────────────────────────────────────────


def test_hc06_positive_has_required_tag():
    """Faculty has the required tag or course has no required tag -> valid."""
    engine = RuleEngine()
    fid = uuid.uuid4()
    faculty = MagicMock(spec=Faculty, id=fid, name="Dr. Sharma")

    c1 = MagicMock(spec=Course, id=uuid.uuid4(), code="CS301", required_expertise_tag="ai_ml")
    c2 = MagicMock(spec=Course, id=uuid.uuid4(), code="CS101", required_expertise_tag=None)

    slots = [
        SimpleSlot(faculty_id=fid, course_id=c1.id),
        SimpleSlot(faculty_id=fid, course_id=c2.id),
    ]
    expertise_map = {fid: {"ai_ml", "python"}}
    courses_map = {c1.id: c1, c2.id: c2}
    fac_map = {fid: faculty}

    violations = engine.check_hc06_faculty_expertise(
        slots,
        faculty_expertise_map=expertise_map,
        courses_map=courses_map,
        faculty_map=fac_map,
    )
    assert len(violations) == 0


def test_hc06_negative_missing_expertise():
    """Course requires a tag that faculty does not possess -> HC-06 violation."""
    engine = RuleEngine()
    fid = uuid.uuid4()
    faculty = MagicMock(spec=Faculty, id=fid, name="Dr. Verma")
    course = MagicMock(spec=Course, id=uuid.uuid4(), code="CS301", name="Machine Learning", required_expertise_tag="ai_ml")

    slot = SimpleSlot(faculty_id=fid, course_id=course.id)
    expertise_map = {fid: {"database", "java"}}  # lacks ai_ml
    courses_map = {course.id: course}
    fac_map = {fid: faculty}

    violations = engine.check_hc06_faculty_expertise(
        [slot],
        faculty_expertise_map=expertise_map,
        courses_map=courses_map,
        faculty_map=fac_map,
    )
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "HC-06"
    assert v.details["required_tag"] == "ai_ml"
    assert fid in v.affected_entity_ids
    assert course.id in v.affected_entity_ids


# ── HC-07: Workload Limits ────────────────────────────────────────────────


def test_hc07_positive_within_limits():
    """Assigned hours in week <= weekly_max_hours -> valid."""
    engine = RuleEngine()
    fid = uuid.uuid4()
    faculty = MagicMock(spec=Faculty, id=fid, name="Dr. Kumar", weekly_max_hours=20.0)

    pid = uuid.uuid4()
    period = MagicMock(spec=Period, id=pid, duration_hours=1.0)

    # 15 hours in the week
    slots = [
        SimpleSlot(
            faculty_id=fid,
            period_id=pid,
            occurrence_date=date(2026, 11, 2) + timedelta(days=i % 5),
        )
        for i in range(15)
    ]

    violations = engine.check_hc07_workload_limits(
        slots, faculty_map={fid: faculty}, periods_map={pid: period}
    )
    assert len(violations) == 0


def test_hc07_negative_workload_exceeded():
    """Assigned hours in week > weekly_max_hours -> HC-07 violation."""
    engine = RuleEngine()
    fid = uuid.uuid4()
    faculty = MagicMock(spec=Faculty, id=fid, name="Dr. Overworked", weekly_max_hours=10.0)

    pid = uuid.uuid4()
    period = MagicMock(spec=Period, id=pid, duration_hours=1.0)

    # 12 hours assigned in the same week
    slots = [
        SimpleSlot(
            faculty_id=fid,
            period_id=pid,
            occurrence_date=date(2026, 11, 2) + timedelta(days=i % 5),
        )
        for i in range(12)
    ]

    violations = engine.check_hc07_workload_limits(
        slots, faculty_map={fid: faculty}, periods_map={pid: period}
    )
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "HC-07"
    assert v.details["assigned_hours"] == 12.0
    assert v.details["weekly_max_hours"] == 10.0
    assert v.details["overload_hours"] == 2.0


# ── HC-08: Data Integrity and References ──────────────────────────────────


def test_hc08_positive_valid_integrity():
    """Known active entities, matching weekday, period end > start -> valid."""
    engine = RuleEngine()
    fid, rid, cid, sid, pid = (uuid.uuid4() for _ in range(5))

    # 2026-11-02 is Monday (weekday 0)
    period = MagicMock(spec=Period, id=pid, weekday=0, start_time=time(9, 0), end_time=time(10, 0))
    slot = SimpleSlot(
        faculty_id=fid,
        room_id=rid,
        course_id=cid,
        section_id=sid,
        period_id=pid,
        occurrence_date=date(2026, 11, 2),
    )

    violations = engine.check_hc08_data_integrity(
        [slot],
        known_faculty_ids={fid},
        known_room_ids={rid},
        known_course_ids={cid},
        known_section_ids={sid},
        known_periods_map={pid: period},
    )
    assert len(violations) == 0


def test_hc08_negative_unknown_entities_and_mismatched_weekday():
    """Unknown entities or weekday mismatch -> HC-08 violations."""
    engine = RuleEngine()
    fid, rid, cid, sid, pid = (uuid.uuid4() for _ in range(5))

    # Period is for Wednesday (weekday 2), but occurrence date is Monday (weekday 0)
    period = MagicMock(spec=Period, id=pid, weekday=2, start_time=time(10, 0), end_time=time(9, 0))  # Also invalid end <= start
    slot = SimpleSlot(
        faculty_id=fid,
        room_id=rid,
        course_id=cid,
        section_id=sid,
        period_id=pid,
        occurrence_date=date(2026, 11, 2),
    )

    # Empty known sets to trigger unknown entity errors
    violations = engine.check_hc08_data_integrity(
        [slot],
        known_faculty_ids=set(),
        known_room_ids=set(),
        known_course_ids=set(),
        known_section_ids=set(),
        known_periods_map={pid: period},
    )
    assert len(violations) >= 3
    rule_ids = {v.rule_id for v in violations}
    assert "HC-08" in rule_ids


# ── HC-09: State Diffing and New Hard Violations Check ─────────────────────


def test_hc09_state_diffing_clean_transition():
    """Resolving baseline violations without adding new ones -> is_valid=True."""
    engine = RuleEngine()

    v1 = Violation(
        rule_id="HC-01",
        constraint_type=ConstraintTypeEnum.hard,
        severity=SeverityEnum.error,
        message="Double booking 1",
        affected_entity_ids=[uuid.uuid4()],
        details={"period_id": "P1"},
    )
    v2 = Violation(
        rule_id="HC-04",
        constraint_type=ConstraintTypeEnum.hard,
        severity=SeverityEnum.error,
        message="Capacity issue",
        affected_entity_ids=[uuid.uuid4()],
        details={"room_id": "R1"},
    )

    # Baseline has v1 and v2
    baseline = [v1, v2]
    # Proposed resolves v1, retains v2
    proposed = [v2]

    diff: ComparisonResult = engine.compare_states(baseline, proposed)
    assert diff.is_valid is True
    assert diff.introduces_new_hard_violations is False
    assert len(diff.resolved_violations) == 1
    assert diff.resolved_violations[0].rule_id == "HC-01"
    assert len(diff.remaining_violations) == 1
    assert len(diff.new_violations) == 0


def test_hc09_state_diffing_rejects_new_hard_violation():
    """A proposed plan introducing a new hard violation must be rejected."""
    engine = RuleEngine()

    v_old = Violation(
        rule_id="HC-01",
        constraint_type=ConstraintTypeEnum.hard,
        severity=SeverityEnum.error,
        message="Existing conflict",
        affected_entity_ids=[uuid.uuid4()],
    )
    v_new = Violation(
        rule_id="HC-02",
        constraint_type=ConstraintTypeEnum.hard,
        severity=SeverityEnum.error,
        message="Newly introduced room conflict",
        affected_entity_ids=[uuid.uuid4()],
    )

    baseline = [v_old]
    proposed = [v_old, v_new]

    diff: ComparisonResult = engine.compare_states(baseline, proposed)
    assert diff.is_valid is False
    assert diff.introduces_new_hard_violations is True
    assert len(diff.new_violations) == 1
    assert diff.new_violations[0].rule_id == "HC-02"


def test_deterministic_signature_consistency():
    """Signatures must be deterministic and identical across separate instances."""
    fid = uuid.uuid4()
    pid = uuid.uuid4()

    v1 = Violation(
        rule_id="HC-01",
        message="Double booked",
        affected_entity_ids=[fid, pid],
        details={"period": str(pid), "faculty": str(fid)},
    )
    v2 = Violation(
        rule_id="HC-01",
        message="Double booked",
        affected_entity_ids=[pid, fid],  # reversed order
        details={"faculty": str(fid), "period": str(pid)},  # reversed key order
    )

    # Both must compute the exact same signature
    assert v1.signature != ""
    assert v1.signature == v2.signature


# ── HC-10: Non-Mutation Verification ──────────────────────────────────────


def test_hc10_non_mutation_verification(db_session: Session):
    """Rule engine validation must not mutate operational database table row counts."""
    engine = RuleEngine(db_session)

    # Take snapshot counts
    snapshot_before = {
        "timetable_entry": db_session.query(TimetableEntry).count(),
        "class_occurrence": db_session.query(ClassOccurrence).count(),
        "faculty": db_session.query(Faculty).count(),
        "faculty_leave": db_session.query(FacultyLeave).count(),
    }

    # Run template validation and dated validation
    _ = engine.validate_timetable_template()
    _ = engine.validate_dated_occurrences()

    # Verify no mutation
    mutations = engine.verify_no_mutation(snapshot_before)
    assert len(mutations) == 0

    # Test artificial mutation detection
    artificial_snapshot = dict(snapshot_before)
    artificial_snapshot["timetable_entry"] += 1
    mutation_violations = engine.verify_no_mutation(artificial_snapshot)
    assert len(mutation_violations) == 1
    assert mutation_violations[0].rule_id == "HC-10"


# ── Soft Preferences: SP-01 to SP-04 ──────────────────────────────────────


def test_soft_preferences_evaluation():
    """Evaluates SP-01 through SP-04 scoring and standard prototype weights."""
    engine = RuleEngine()
    dept_id = uuid.uuid4()

    faculty = MagicMock(spec=Faculty, id=uuid.uuid4(), department_id=dept_id, weekly_max_hours=20.0)
    course = MagicMock(spec=Course, id=uuid.uuid4(), department_id=dept_id, required_expertise_tag="ai_ml")
    section = MagicMock(spec=Section, id=uuid.uuid4())

    # Candidate with primary expertise, 5h assigned (25% utilization), teaches section, same dept
    results = engine.evaluate_soft_preferences(
        candidate_faculty=faculty,
        course=course,
        section=section,
        assigned_hours_this_week=5.0,
        already_teaches_course_or_section=True,
        faculty_expertise_level=ExpertiseLevelEnum.primary,
    )

    assert len(results) == 4
    by_pref = {r.preference_id: r for r in results}

    # SP-01: Primary expertise -> score 1.0, weight 0.35
    assert by_pref["SP-01"].score == 1.0
    assert by_pref["SP-01"].weight == 0.35
    assert by_pref["SP-01"].weighted_score == 0.35

    # SP-02: Workload balance: 5/20 = 25% -> score 0.75, weight 0.30
    assert by_pref["SP-02"].score == 0.75
    assert by_pref["SP-02"].weight == 0.30
    assert by_pref["SP-02"].weighted_score == round(0.75 * 0.30, 4)

    # SP-03: Teaching continuity: True -> score 1.0, weight 0.25
    assert by_pref["SP-03"].score == 1.0
    assert by_pref["SP-03"].weight == 0.25
    assert by_pref["SP-03"].weighted_score == 0.25

    # SP-04: Same department: True -> score 1.0, weight 0.10
    assert by_pref["SP-04"].score == 1.0
    assert by_pref["SP-04"].weight == 0.10
    assert by_pref["SP-04"].weighted_score == 0.10


# ── Seeded Database Verification (Planted Conflicts) ──────────────────────


def test_seeded_planted_conflicts_detection(db_session: Session):
    """
    Assert that all 5 planted conflicts in the synthetic seed are detected by RuleEngine:
    1. HC-01: Dr. Arun Kumar double-booked on Mon P1
    2. HC-02: Room 301 double-booked on Tue P3
    3. HC-04: CS-1A (enrollment 65) in Room 101 (capacity 60) on Thu P1
    4. HC-05: CS402 (requires_lab=True) in Room 101 (is_lab=False) on Fri P5
    5. HC-06: Dr. Sanjay Verma (no ML expertise) assigned CS301 on Fri P6
    """
    engine = RuleEngine(db_session)
    result: RuleValidationResult = engine.validate_timetable_template()

    assert result.is_valid is False
    assert result.hard_violations_count >= 5

    # Check that every planted rule has at least one violation
    planted_rules = {"HC-01", "HC-02", "HC-04", "HC-05", "HC-06"}
    detected_rules = set(result.by_rule.keys())
    assert planted_rules.issubset(detected_rules), f"Missing detection of {planted_rules - detected_rules}"

    # Verify HC-01 mentions double booking
    hc01_violations = result.by_rule["HC-01"]
    assert len(hc01_violations) >= 1
    assert any(len(v.affected_entity_ids) >= 2 for v in hc01_violations)

    # Verify HC-04 details include deficit
    hc04_violations = result.by_rule["HC-04"]
    assert len(hc04_violations) >= 1
    assert any(v.details.get("deficit") == 5 for v in hc04_violations)

    # Verify HC-05 details include room_is_lab is False
    hc05_violations = result.by_rule["HC-05"]
    assert len(hc05_violations) >= 1
    assert any(v.details.get("room_is_lab") is False for v in hc05_violations)


def test_seeded_hero_leave_dated_detection(db_session: Session):
    """
    On 2026-11-02 (Mon), Dr. Raj Sharma is on approved leave.
    Validating dated occurrences on this day must flag HC-03 violations.
    """
    engine = RuleEngine(db_session)
    hero_date = date(2026, 11, 2)

    result: RuleValidationResult = engine.validate_dated_occurrences(target_date=hero_date)

    assert result.is_valid is False
    assert "HC-03" in result.by_rule
    hc03_violations = result.by_rule["HC-03"]
    # Dr. Sharma has classes on Monday (Mon P2 and Mon P4 in seed)
    assert len(hc03_violations) >= 2
    for v in hc03_violations:
        assert v.details["occurrence_date"] == str(hero_date)
        assert any(e.ref_type == "leave" for e in v.evidence_refs)


# ── API Endpoint Tests ────────────────────────────────────────────────────


def test_get_conflicts_unauthenticated(client: TestClient):
    """GET /conflicts must return 401 without token."""
    response = client.get("/conflicts")
    assert response.status_code == 401


def test_get_conflicts_authenticated(seeded_client: TestClient):
    """GET /conflicts with valid credentials returns structured conflicts."""
    # Login as principal
    login_res = seeded_client.post(
        "/auth/token",
        data={"username": "principal@campus.os", "password": "changeme"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    response = seeded_client.get(
        "/conflicts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_valid"] is False
    assert body["total_conflicts"] >= 5
    assert body["hard_conflicts"] >= 5
    assert body["evaluation_scope"] == "template"
    assert "HC-01" in body["by_rule"]
    assert "HC-02" in body["by_rule"]
    assert "HC-04" in body["by_rule"]
    assert "HC-05" in body["by_rule"]
    assert "HC-06" in body["by_rule"]


def test_get_conflicts_dated_occurrences(seeded_client: TestClient):
    """GET /conflicts?date=2026-11-02 returns HC-03 leave conflicts."""
    login_res = seeded_client.post(
        "/auth/token",
        data={"username": "principal@campus.os", "password": "changeme"},
    )
    token = login_res.json()["access_token"]

    response = seeded_client.get(
        "/conflicts?date=2026-11-02",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation_scope"] == "dated_occurrences"
    assert body["target_date"] == "2026-11-02"
    assert "HC-03" in body["by_rule"]


def test_get_workload_endpoint(seeded_client: TestClient):
    """GET /workload returns per-faculty capacity utilization and metrics."""
    login_res = seeded_client.post(
        "/auth/token",
        data={"username": "hod.cs@campus.os", "password": "changeme"},
    )
    token = login_res.json()["access_token"]

    response = seeded_client.get(
        "/workload?week_date=2026-11-02",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["week_start"] == "2026-11-02"
    assert body["week_end"] == "2026-11-08"
    assert body["total_faculty"] >= 30
    assert len(body["faculty_workloads"]) >= 30
    assert "avg_hours" in body
    assert "max_hours" in body


def test_dashboard_uses_rule_engine(seeded_client: TestClient):
    """GET /dashboard conflict count reflects authoritative rule engine result."""
    login_res = seeded_client.post(
        "/auth/token",
        data={"username": "principal@campus.os", "password": "changeme"},
    )
    token = login_res.json()["access_token"]

    response = seeded_client.get(
        "/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["conflict_count"] >= 5
    rule_ids = {c["rule_id"] for c in body["conflicts_summary"]}
    assert "HC-01" in rule_ids
    assert "HC-02" in rule_ids
    assert "HC-04" in rule_ids
    assert "HC-05" in rule_ids
    assert "HC-06" in rule_ids
    assert any("Authoritative check from deterministic rule engine" in c["note"] for c in body["conflicts_summary"])

