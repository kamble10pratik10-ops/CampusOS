"""
Timetable and occurrence services.

Includes on-demand class_occurrence generation for dates outside the
pre-seeded 6-week window (approved in M0 review).

Weekly workload calculation:
    Uses actual period duration (end_time - start_time in hours),
    aggregated over the Monday-Sunday calendar week containing the target date.
    This is consistent with HC-07 as implemented in the rule engine (M2).
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import ClassOccurrence, OccurrenceStatusEnum, Period, TimetableEntry


def week_bounds(d: date) -> tuple[date, date]:
    """Return (monday, sunday) of the calendar week containing date d."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def dates_for_weekday_in_range(weekday: int, start: date, end: date) -> list[date]:
    """All dates in [start, end] (inclusive) whose weekday matches (0=Mon)."""
    days_ahead = (weekday - start.weekday()) % 7
    first = start + timedelta(days=days_ahead)
    result: list[date] = []
    current = first
    while current <= end:
        result.append(current)
        current += timedelta(weeks=1)
    return result


def ensure_occurrences_for_range(db: Session, start_date: date, end_date: date) -> int:
    """
    Idempotent: generate class_occurrence rows for all timetable_entries
    whose period weekday falls within [start_date, end_date].

    Uses ON CONFLICT DO NOTHING so duplicate calls are safe.
    Returns the number of newly created rows.

    This is the on-demand generation path called when a query requests
    dates outside the pre-seeded window.
    """
    import random

    rows_q = db.execute(
        text("""
            SELECT te.id AS entry_id, p.weekday
            FROM timetable_entry te
            JOIN period p ON te.period_id = p.id
        """)
    ).fetchall()

    occurrence_rows: list[dict] = []
    for row in rows_q:
        for d in dates_for_weekday_in_range(row.weekday, start_date, end_date):
            occurrence_rows.append({
                "id": uuid.uuid4(),
                "timetable_entry_id": row.entry_id,
                "occurrence_date": d,
                "override_faculty_id": None,
                "override_room_id": None,
                "status": OccurrenceStatusEnum.scheduled,
            })

    if not occurrence_rows:
        return 0

    stmt = pg_insert(ClassOccurrence).values(occurrence_rows).on_conflict_do_nothing(
        index_elements=["timetable_entry_id", "occurrence_date"]
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount if result.rowcount >= 0 else 0


def get_occurrences_on_date(db: Session, target_date: date) -> list[dict[str, Any]]:
    """
    Return class occurrences on target_date.
    Auto-generates occurrences if none exist for that date (on-demand generation).
    """
    existing = db.execute(
        text("SELECT COUNT(*) FROM class_occurrence WHERE occurrence_date = :d"),
        {"d": target_date},
    ).scalar()

    if existing == 0:
        ensure_occurrences_for_range(db, target_date, target_date)

    rows = db.execute(
        text("""
            SELECT
                co.id,
                co.occurrence_date,
                co.status,
                te.section_id,
                s.name AS section_name,
                te.course_id,
                c.name AS course_name,
                COALESCE(co.override_faculty_id, te.faculty_id) AS effective_faculty_id,
                f.name AS faculty_name,
                COALESCE(co.override_room_id, te.room_id) AS effective_room_id,
                r.name AS room_name,
                p.start_time,
                p.end_time,
                p.weekday,
                p.label AS period_label
            FROM class_occurrence co
            JOIN timetable_entry te ON co.timetable_entry_id = te.id
            JOIN section s ON te.section_id = s.id
            JOIN course c ON te.course_id = c.id
            JOIN faculty f ON COALESCE(co.override_faculty_id, te.faculty_id) = f.id
            JOIN room r ON COALESCE(co.override_room_id, te.room_id) = r.id
            JOIN period p ON te.period_id = p.id
            WHERE co.occurrence_date = :d
            ORDER BY p.weekday, p.start_time
        """),
        {"d": target_date},
    ).fetchall()
    return [dict(row._mapping) for row in rows]


def get_timetable_stats(db: Session, department_id: uuid.UUID | None = None) -> dict[str, int]:
    """Aggregate counts for the dashboard (optionally department-filtered)."""
    if department_id is not None:
        result = db.execute(
            text("""
                SELECT
                    (SELECT COUNT(*) FROM timetable_entry te JOIN course c ON te.course_id = c.id WHERE c.department_id = :dept_id) AS total_entries,
                    (SELECT COUNT(*) FROM faculty WHERE is_active = true AND department_id = :dept_id) AS total_faculty,
                    (SELECT COUNT(*) FROM course WHERE department_id = :dept_id) AS total_courses,
                    (SELECT COUNT(*) FROM section WHERE department_id = :dept_id) AS total_sections,
                    (SELECT COUNT(*) FROM room WHERE is_active = true) AS total_rooms
            """),
            {"dept_id": department_id},
        ).fetchone()
    else:
        result = db.execute(
            text("""
                SELECT
                    (SELECT COUNT(*) FROM timetable_entry) AS total_entries,
                    (SELECT COUNT(*) FROM faculty WHERE is_active = true) AS total_faculty,
                    (SELECT COUNT(*) FROM course) AS total_courses,
                    (SELECT COUNT(*) FROM section) AS total_sections,
                    (SELECT COUNT(*) FROM room WHERE is_active = true) AS total_rooms
            """)
        ).fetchone()
    return dict(result._mapping)


def get_occurrences_count_for_week(db: Session, week_monday: date, department_id: uuid.UUID | None = None) -> int:
    """Count class occurrences in the Mon–Sun week starting at week_monday."""
    week_sunday = week_monday + timedelta(days=6)
    if department_id is not None:
        return db.execute(
            text("""
                SELECT COUNT(*) FROM class_occurrence co
                JOIN timetable_entry te ON co.timetable_entry_id = te.id
                JOIN course c ON te.course_id = c.id
                WHERE c.department_id = :dept_id
                AND co.occurrence_date BETWEEN :mon AND :sun
                AND co.status != 'cancelled'
            """),
            {"mon": week_monday, "sun": week_sunday, "dept_id": department_id},
        ).scalar() or 0
    return db.execute(
        text("""
            SELECT COUNT(*) FROM class_occurrence
            WHERE occurrence_date BETWEEN :mon AND :sun
            AND status != 'cancelled'
        """),
        {"mon": week_monday, "sun": week_sunday},
    ).scalar() or 0


def get_faculty_on_leave_on(db: Session, target_date: date, department_id: uuid.UUID | None = None) -> int:
    """Count active faculty on leave on target_date (inclusive boundary check)."""
    if department_id is not None:
        return db.execute(
            text("""
                SELECT COUNT(DISTINCT fl.faculty_id)
                FROM faculty_leave fl
                JOIN faculty f ON fl.faculty_id = f.id
                WHERE f.is_active = true
                AND f.department_id = :dept_id
                AND fl.start_date <= :d
                AND fl.end_date >= :d
            """),
            {"d": target_date, "dept_id": department_id},
        ).scalar() or 0
    return db.execute(
        text("""
            SELECT COUNT(DISTINCT fl.faculty_id)
            FROM faculty_leave fl
            JOIN faculty f ON fl.faculty_id = f.id
            WHERE f.is_active = true
            AND fl.start_date <= :d
            AND fl.end_date >= :d
        """),
        {"d": target_date},
    ).scalar() or 0


def get_conflict_counts(db: Session) -> list[dict[str, Any]]:
    """
    M1 approximation of conflict detection.
    These direct SQL queries will be replaced by the deterministic rule engine in M2.
    Each count should match the planted violations in the seed data.

    Limitation: These queries check the timetable_entry template only.
    The full rule engine (M2) checks dated class_occurrences and accounts
    for overrides, leave boundaries, and existing-vs-new distinction.
    """
    hc01 = db.execute(
        text("""
            SELECT COUNT(*) FROM (
                SELECT faculty_id, period_id
                FROM timetable_entry
                GROUP BY faculty_id, period_id
                HAVING COUNT(*) > 1
            ) t
        """)
    ).scalar() or 0

    hc02 = db.execute(
        text("""
            SELECT COUNT(*) FROM (
                SELECT room_id, period_id
                FROM timetable_entry
                GROUP BY room_id, period_id
                HAVING COUNT(*) > 1
            ) t
        """)
    ).scalar() or 0

    hc04 = db.execute(
        text("""
            SELECT COUNT(*)
            FROM timetable_entry te
            JOIN section s ON te.section_id = s.id
            JOIN room r ON te.room_id = r.id
            WHERE s.enrollment > r.capacity
        """)
    ).scalar() or 0

    hc05 = db.execute(
        text("""
            SELECT COUNT(*)
            FROM timetable_entry te
            JOIN course c ON te.course_id = c.id
            JOIN room r ON te.room_id = r.id
            WHERE c.requires_lab = true AND r.is_lab = false
        """)
    ).scalar() or 0

    hc06 = db.execute(
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
    ).scalar() or 0

    return [
        {
            "rule_id": "HC-01",
            "description": "Faculty assigned to overlapping class periods",
            "count": hc01,
            "note": "M1 approximation: checks timetable_entry template only",
        },
        {
            "rule_id": "HC-02",
            "description": "Room hosting overlapping classes",
            "count": hc02,
            "note": "M1 approximation: checks timetable_entry template only",
        },
        {
            "rule_id": "HC-04",
            "description": "Room capacity below section enrollment",
            "count": hc04,
            "note": "M1 approximation: checks timetable_entry template only",
        },
        {
            "rule_id": "HC-05",
            "description": "Lab course assigned to non-lab room",
            "count": hc05,
            "note": "M1 approximation: checks timetable_entry template only",
        },
        {
            "rule_id": "HC-06",
            "description": "Faculty lacks required course expertise",
            "count": hc06,
            "note": "M1 approximation: checks timetable_entry template only",
        },
    ]


def get_workload_this_week(
    db: Session,
    week_monday: date,
    week_sunday: date,
    department_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Compute workload summary for the given Mon–Sun week.

    Workload = SUM of period durations (actual hours, not assumed 1h)
    for all class_occurrences in the week where the faculty is the
    assigned teacher (including overrides).
    """
    query_str = """
        SELECT
            COALESCE(co.override_faculty_id, te.faculty_id) AS faculty_id,
            f.name AS faculty_name,
            f.weekly_max_hours,
            SUM(
                EXTRACT(EPOCH FROM (p.end_time - p.start_time)) / 3600.0
            ) AS total_hours
        FROM class_occurrence co
        JOIN timetable_entry te ON co.timetable_entry_id = te.id
        JOIN period p ON te.period_id = p.id
        JOIN faculty f ON COALESCE(co.override_faculty_id, te.faculty_id) = f.id
        WHERE co.occurrence_date BETWEEN :mon AND :sun
        AND co.status != 'cancelled'
    """
    params: dict[str, Any] = {"mon": week_monday, "sun": week_sunday}
    if department_id is not None:
        query_str += " AND f.department_id = :dept_id"
        params["dept_id"] = department_id

    query_str += """
        GROUP BY
            COALESCE(co.override_faculty_id, te.faculty_id),
            f.name, f.weekly_max_hours
        ORDER BY total_hours DESC
    """
    rows = db.execute(text(query_str), params).fetchall()

    if not rows:
        return {
            "avg_hours_this_week": 0.0,
            "max_hours_this_week": 0.0,
            "min_hours_this_week": 0.0,
            "overloaded_count": 0,
        }

    hours = [float(r.total_hours) for r in rows]
    overloaded = sum(1 for r in rows if float(r.total_hours) > float(r.weekly_max_hours))
    return {
        "avg_hours_this_week": round(sum(hours) / len(hours), 2),
        "max_hours_this_week": round(max(hours), 2),
        "min_hours_this_week": round(min(hours), 2),
        "overloaded_count": overloaded,
    }
