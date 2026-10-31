"""
test_seed.py — M1 seed data verification tests.

These tests verify that:
    - All expected entities are seeded with the correct counts
    - Fixed UUIDs for critical demo entities are stable
    - Hero scenario leave record exists and covers the right dates
    - Planted violations exist in the timetable template
    - Class occurrences are generated for the 6-week window
    - Temporal boundary correctness (leave covers Mon-Wed, not Fri)

All data is SYNTHETIC.  No real institutional data is used.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.seed import (
    DEPT_CS_ID,
    DEPT_EC_ID,
    DEPT_ME_ID,
    HERO_LEAVE_ID,
    OCCURRENCE_WINDOW_END,
    OCCURRENCE_WINDOW_START,
    ROOM_101_ID,
    SHARMA_ID,
    USER_HOD_CS_ID,
    USER_PRINCIPAL_ID,
    run_seed,
)


@pytest.fixture(scope="module")
def seeded_db(test_engine):
    """
    Module-scoped: uses the session-seeded database.
    """
    with Session(test_engine) as session:
        yield session


# ── Department counts ─────────────────────────────────────────────────────


def test_department_count(seeded_db: Session) -> None:
    count = seeded_db.execute(text("SELECT COUNT(*) FROM department")).scalar()
    assert count == 3, f"Expected 3 departments, got {count}"


def test_department_fixed_ids(seeded_db: Session) -> None:
    for dept_id in (DEPT_CS_ID, DEPT_EC_ID, DEPT_ME_ID):
        row = seeded_db.execute(
            text("SELECT id FROM department WHERE id = :id"), {"id": dept_id}
        ).fetchone()
        assert row is not None, f"Department {dept_id} not found"


# ── User counts ───────────────────────────────────────────────────────────


def test_user_count(seeded_db: Session) -> None:
    count = seeded_db.execute(text('SELECT COUNT(*) FROM "user"')).scalar()
    assert count == 4, f"Expected 4 users, got {count}"


def test_principal_user(seeded_db: Session) -> None:
    row = seeded_db.execute(
        text('SELECT role, department_id FROM "user" WHERE id = :id'),
        {"id": USER_PRINCIPAL_ID},
    ).fetchone()
    assert row is not None
    assert row.role == "principal"
    assert row.department_id is None  # Principal has institution-wide access


def test_hod_has_department(seeded_db: Session) -> None:
    row = seeded_db.execute(
        text('SELECT role, department_id FROM "user" WHERE id = :id'),
        {"id": USER_HOD_CS_ID},
    ).fetchone()
    assert row is not None
    assert row.role == "hod"
    assert row.department_id == DEPT_CS_ID


# ── Faculty counts ────────────────────────────────────────────────────────


def test_faculty_count(seeded_db: Session) -> None:
    count = seeded_db.execute(
        text("SELECT COUNT(*) FROM faculty WHERE is_active = true")
    ).scalar()
    assert count == 30, f"Expected 30 active faculty, got {count}"


def test_hero_faculty_exists(seeded_db: Session) -> None:
    row = seeded_db.execute(
        text("SELECT employee_code, name FROM faculty WHERE id = :id"),
        {"id": SHARMA_ID},
    ).fetchone()
    assert row is not None
    assert row.employee_code == "CS001"
    assert "Sharma" in row.name


# ── Course counts ─────────────────────────────────────────────────────────


def test_course_count(seeded_db: Session) -> None:
    count = seeded_db.execute(text("SELECT COUNT(*) FROM course")).scalar()
    assert count == 40, f"Expected 40 courses, got {count}"


# ── Section counts ────────────────────────────────────────────────────────


def test_section_count(seeded_db: Session) -> None:
    count = seeded_db.execute(text("SELECT COUNT(*) FROM section")).scalar()
    assert count == 12, f"Expected 12 sections, got {count}"


# ── Room counts ───────────────────────────────────────────────────────────


def test_room_count(seeded_db: Session) -> None:
    count = seeded_db.execute(
        text("SELECT COUNT(*) FROM room WHERE is_active = true")
    ).scalar()
    assert count == 15, f"Expected 15 active rooms, got {count}"


def test_lab_count(seeded_db: Session) -> None:
    count = seeded_db.execute(
        text("SELECT COUNT(*) FROM room WHERE is_lab = true AND is_active = true")
    ).scalar()
    assert count == 5, f"Expected 5 labs, got {count}"


# ── Period counts ─────────────────────────────────────────────────────────


def test_period_count(seeded_db: Session) -> None:
    count = seeded_db.execute(text("SELECT COUNT(*) FROM period")).scalar()
    assert count == 30, f"Expected 30 periods (6 slots × 5 days), got {count}"


# ── Timetable entries ─────────────────────────────────────────────────────


def test_timetable_entries_exist(seeded_db: Session) -> None:
    count = seeded_db.execute(text("SELECT COUNT(*) FROM timetable_entry")).scalar()
    assert count > 0, "No timetable entries found"


def test_hero_entries_exist(seeded_db: Session) -> None:
    """Dr. Sharma has 9 timetable entries (6 affected during Mon-Wed leave + 3 unaffected)."""
    count = seeded_db.execute(
        text("SELECT COUNT(*) FROM timetable_entry WHERE faculty_id = :fid"),
        {"fid": SHARMA_ID},
    ).scalar()
    assert count == 9, f"Expected 9 entries for Dr. Sharma, got {count}"


# ── Planted violations ────────────────────────────────────────────────────


def test_hc01_planted(seeded_db: Session) -> None:
    """HC-01: At least one faculty is double-booked in the same period."""
    count = seeded_db.execute(
        text("""
            SELECT COUNT(*) FROM (
                SELECT faculty_id, period_id
                FROM timetable_entry
                GROUP BY faculty_id, period_id
                HAVING COUNT(*) > 1
            ) t
        """)
    ).scalar()
    assert count >= 1, "HC-01 violation (faculty double-booking) not found"


def test_hc02_planted(seeded_db: Session) -> None:
    """HC-02: At least one room is double-booked in the same period."""
    count = seeded_db.execute(
        text("""
            SELECT COUNT(*) FROM (
                SELECT room_id, period_id
                FROM timetable_entry
                GROUP BY room_id, period_id
                HAVING COUNT(*) > 1
            ) t
        """)
    ).scalar()
    assert count >= 1, "HC-02 violation (room double-booking) not found"


def test_hc04_planted(seeded_db: Session) -> None:
    """HC-04: Room 101 (capacity 60) is assigned to CS-1A (enrollment 65)."""
    count = seeded_db.execute(
        text("""
            SELECT COUNT(*)
            FROM timetable_entry te
            JOIN section s ON te.section_id = s.id
            JOIN room r ON te.room_id = r.id
            WHERE s.enrollment > r.capacity
        """)
    ).scalar()
    assert count >= 1, "HC-04 violation (capacity) not found"


def test_hc05_planted(seeded_db: Session) -> None:
    """HC-05: Lab course CS402 assigned to non-lab Room 101."""
    count = seeded_db.execute(
        text("""
            SELECT COUNT(*)
            FROM timetable_entry te
            JOIN course c ON te.course_id = c.id
            JOIN room r ON te.room_id = r.id
            WHERE c.requires_lab = true AND r.is_lab = false
        """)
    ).scalar()
    assert count >= 1, "HC-05 violation (lab room requirement) not found"


def test_hc06_planted(seeded_db: Session) -> None:
    """HC-06: Sanjay Verma (no ML expertise) assigned CS301 Machine Learning."""
    count = seeded_db.execute(
        text("""
            SELECT COUNT(*)
            FROM timetable_entry te
            JOIN course c ON te.course_id = c.id
            WHERE c.required_expertise_tag IS NOT NULL
            AND te.faculty_id NOT IN (
                SELECT faculty_id FROM faculty_expertise
                WHERE course_tag = c.required_expertise_tag
            )
        """)
    ).scalar()
    assert count >= 1, "HC-06 violation (expertise) not found"


# ── Hero leave record ─────────────────────────────────────────────────────


def test_hero_leave_exists(seeded_db: Session) -> None:
    """Dr. Sharma's leave must exist with the fixed HERO_LEAVE_ID."""
    row = seeded_db.execute(
        text("""
            SELECT faculty_id, start_date, end_date
            FROM faculty_leave WHERE id = :lid
        """),
        {"lid": HERO_LEAVE_ID},
    ).fetchone()
    assert row is not None, "Hero leave record not found"
    assert row.faculty_id == SHARMA_ID
    assert row.start_date == date(2026, 11, 2)
    assert row.end_date == date(2026, 11, 4)


def test_hero_leave_covers_mon_to_wed(seeded_db: Session) -> None:
    """Leave covers 2026-11-02 (Mon) through 2026-11-04 (Wed) inclusive."""
    row = seeded_db.execute(
        text("SELECT start_date, end_date FROM faculty_leave WHERE id = :lid"),
        {"lid": HERO_LEAVE_ID},
    ).fetchone()
    assert row.start_date <= date(2026, 11, 2)
    assert row.end_date >= date(2026, 11, 4)


def test_hero_leave_does_not_cover_friday(seeded_db: Session) -> None:
    """Leave must NOT cover 2026-11-06 (Fri) — Sharma's Fri P1 is unaffected."""
    row = seeded_db.execute(
        text("SELECT start_date, end_date FROM faculty_leave WHERE id = :lid"),
        {"lid": HERO_LEAVE_ID},
    ).fetchone()
    friday = date(2026, 11, 6)
    assert not (row.start_date <= friday <= row.end_date), \
        "Leave incorrectly covers Friday"


# ── Class occurrences ─────────────────────────────────────────────────────


def test_occurrences_generated(seeded_db: Session) -> None:
    """Class occurrences must be pre-generated for the 6-week window."""
    count = seeded_db.execute(text("SELECT COUNT(*) FROM class_occurrence")).scalar()
    assert count > 0, "No class occurrences found — seed may have failed"


def test_occurrences_cover_hero_dates(seeded_db: Session) -> None:
    """Occurrences must exist for 2026-11-02 (Mon) — hero scenario start."""
    count = seeded_db.execute(
        text("SELECT COUNT(*) FROM class_occurrence WHERE occurrence_date = '2026-11-02'")
    ).scalar()
    assert count > 0, "No occurrences for hero leave start date 2026-11-02"


def test_occurrences_within_window(seeded_db: Session) -> None:
    """All occurrences must fall within the seeded window."""
    out_of_window = seeded_db.execute(
        text("""
            SELECT COUNT(*) FROM class_occurrence
            WHERE occurrence_date < :start OR occurrence_date > :end
        """),
        {"start": OCCURRENCE_WINDOW_START, "end": OCCURRENCE_WINDOW_END},
    ).scalar()
    assert out_of_window == 0, f"{out_of_window} occurrences fall outside the seeded window"


def test_occurrence_unique_per_entry_per_date(seeded_db: Session) -> None:
    """No duplicate (timetable_entry_id, occurrence_date) pairs."""
    duplicates = seeded_db.execute(
        text("""
            SELECT COUNT(*) FROM (
                SELECT timetable_entry_id, occurrence_date
                FROM class_occurrence
                GROUP BY timetable_entry_id, occurrence_date
                HAVING COUNT(*) > 1
            ) t
        """)
    ).scalar()
    assert duplicates == 0, f"{duplicates} duplicate occurrence records found"

