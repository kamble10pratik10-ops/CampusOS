"""
Deterministic synthetic data seed for Campus OS.

⚠  ALL DATA IS SYNTHETIC AND DOES NOT REPRESENT ANY REAL INSTITUTION. ⚠

Run:
    python -m app.db.seed              # seeds the configured DATABASE_URL
    python -m app.db.seed --reset      # drops and recreates all tables first

Design:
    - RNG seeded with SEED=42 so the same data is produced on every run.
    - Critical demo entities (hero professor, demo users) use fixed UUIDs
      so foreign keys remain stable across re-seeds.
    - Seed is IDEMPOTENT: uses ON CONFLICT DO NOTHING where possible.
    - 5 deliberately planted constraint violations are documented inline
      for the rule engine (M2) to detect.

Hero scenario:
    Dr. Raj Sharma (CS dept) is on leave 2026-11-02 (Mon) to 2026-11-04 (Wed).
    DEMO_TODAY = 2026-10-26 (Mon), so this is "next week Mon-Wed".
    Affected class occurrences: Mon P2, Mon P4, Tue P1, Tue P3, Wed P1, Wed P2.

Planted conflicts (detected by rule engine in M2):
    HC-01: Dr. Arun Kumar double-booked on Mon P1 (CS-1A and CS-2A).
    HC-02: Room 301 double-booked on Tue P3 (EC-1A and ME-1A).
    HC-04: CS-1A (enrollment=65) in Room 101 (capacity=60) on Thu P1.
    HC-05: CS402 Mobile Computing (requires_lab=True) in Room 101 (not a lab) on Fri P5.
    HC-06: Dr. Sanjay Verma (no ML expertise) assigned CS301 Machine Learning on Fri P6.
"""
from __future__ import annotations

import sys
import uuid
import random
import logging
from datetime import date, time, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    ClassOccurrence,
    Course,
    CourseTag,
    Decision,
    Department,
    ExpertiseLevelEnum,
    Faculty,
    FacultyExpertise,
    FacultyLeave,
    OccurrenceStatusEnum,
    Period,
    RoleEnum,
    Room,
    Section,
    TimetableEntry,
    User,
)
from app.db.session import SessionLocal, engine
from app.core.security import get_password_hash
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Seeding constants ─────────────────────────────────────────────────────

SEED = 42
_rng = random.Random(SEED)

DEMO_TODAY = date(2026, 10, 26)           # Fixed demo date
OCCURRENCE_WINDOW_START = date(2026, 10, 19)   # 6-week window start (Mon)
OCCURRENCE_WINDOW_END = date(2026, 11, 29)     # 6-week window end

# ── Fixed UUIDs for critical demo entities ────────────────────────────────
# Using fixed UUIDs keeps foreign keys stable across re-seeds.

DEPT_CS_ID   = uuid.UUID("10000000-0000-0000-0000-000000000001")
DEPT_EC_ID   = uuid.UUID("10000000-0000-0000-0000-000000000002")
DEPT_ME_ID   = uuid.UUID("10000000-0000-0000-0000-000000000003")

USER_PRINCIPAL_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
USER_HOD_CS_ID    = uuid.UUID("20000000-0000-0000-0000-000000000002")
USER_HOD_EC_ID    = uuid.UUID("20000000-0000-0000-0000-000000000003")
USER_HOD_ME_ID    = uuid.UUID("20000000-0000-0000-0000-000000000004")

SHARMA_ID         = uuid.UUID("30000000-0000-0000-0000-000000000001")  # hero professor
ARUN_KUMAR_ID     = uuid.UUID("30000000-0000-0000-0000-000000000003")  # HC-01 planted
SANJAY_VERMA_ID   = uuid.UUID("30000000-0000-0000-0000-000000000009")  # HC-06 planted

ROOM_101_ID = uuid.UUID("50000000-0000-0000-0000-000000000001")
ROOM_102_ID = uuid.UUID("50000000-0000-0000-0000-000000000002")
ROOM_201_ID = uuid.UUID("50000000-0000-0000-0000-000000000004")
ROOM_202_ID = uuid.UUID("50000000-0000-0000-0000-000000000005")
ROOM_301_ID = uuid.UUID("50000000-0000-0000-0000-000000000007")  # HC-02 planted

HERO_LEAVE_ID = uuid.UUID("70000000-0000-0000-0000-000000000001")


def _rng_uuid() -> uuid.UUID:
    """Generate a deterministic UUID from the seeded RNG."""
    return uuid.UUID(int=_rng.getrandbits(128))


def dates_for_weekday_in_range(weekday: int, start: date, end: date) -> list[date]:
    """
    Return all dates in [start, end] (inclusive) whose weekday matches.
    weekday: 0=Monday … 6=Sunday
    """
    days_ahead = (weekday - start.weekday()) % 7
    first = start + timedelta(days=days_ahead)
    result: list[date] = []
    current = first
    while current <= end:
        result.append(current)
        current += timedelta(weeks=1)
    return result


# ── Seed functions ────────────────────────────────────────────────────────


def seed_departments(db: Session) -> dict[str, uuid.UUID]:
    """Seed 3 departments. Returns {code: id}."""
    rows = [
        {"id": DEPT_CS_ID, "name": "Computer Science", "code": "CS"},
        {"id": DEPT_EC_ID, "name": "Electronics & Communication", "code": "EC"},
        {"id": DEPT_ME_ID, "name": "Mechanical Engineering", "code": "ME"},
    ]
    stmt = pg_insert(Department).values(rows).on_conflict_do_nothing(index_elements=["code"])
    db.execute(stmt)
    db.flush()
    return {"CS": DEPT_CS_ID, "EC": DEPT_EC_ID, "ME": DEPT_ME_ID}


def seed_users(db: Session, dept_ids: dict[str, uuid.UUID]) -> None:
    """Seed 4 demo users: 1 principal + 3 HODs."""
    pwd_hash = get_password_hash(settings.DEMO_PASSWORD)
    rows = [
        {
            "id": USER_PRINCIPAL_ID,
            "email": "principal@campus.os",
            "hashed_password": pwd_hash,
            "role": RoleEnum.principal,
            "department_id": None,
            "is_active": True,
        },
        {
            "id": USER_HOD_CS_ID,
            "email": "hod.cs@campus.os",
            "hashed_password": pwd_hash,
            "role": RoleEnum.hod,
            "department_id": dept_ids["CS"],
            "is_active": True,
        },
        {
            "id": USER_HOD_EC_ID,
            "email": "hod.ec@campus.os",
            "hashed_password": pwd_hash,
            "role": RoleEnum.hod,
            "department_id": dept_ids["EC"],
            "is_active": True,
        },
        {
            "id": USER_HOD_ME_ID,
            "email": "hod.me@campus.os",
            "hashed_password": pwd_hash,
            "role": RoleEnum.hod,
            "department_id": dept_ids["ME"],
            "is_active": True,
        },
    ]
    stmt = pg_insert(User).values(rows).on_conflict_do_nothing(index_elements=["email"])
    db.execute(stmt)
    db.flush()


def seed_rooms(db: Session) -> dict[str, uuid.UUID]:
    """Seed 15 rooms (10 classrooms + 5 labs). Returns {name: id}."""
    rooms = [
        # Regular classrooms
        {"id": ROOM_101_ID, "name": "Room 101", "capacity": 60, "is_lab": False, "is_active": True},
        {"id": ROOM_102_ID, "name": "Room 102", "capacity": 60, "is_lab": False, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000003"), "name": "Room 103", "capacity": 60, "is_lab": False, "is_active": True},
        {"id": ROOM_201_ID, "name": "Room 201", "capacity": 60, "is_lab": False, "is_active": True},
        {"id": ROOM_202_ID, "name": "Room 202", "capacity": 60, "is_lab": False, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000006"), "name": "Room 203", "capacity": 60, "is_lab": False, "is_active": True},
        {"id": ROOM_301_ID, "name": "Room 301", "capacity": 60, "is_lab": False, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000008"), "name": "Room 302", "capacity": 60, "is_lab": False, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000009"), "name": "Seminar Hall A", "capacity": 120, "is_lab": False, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000010"), "name": "Seminar Hall B", "capacity": 120, "is_lab": False, "is_active": True},
        # Labs
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000011"), "name": "CS Lab 1", "capacity": 40, "is_lab": True, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000012"), "name": "CS Lab 2", "capacity": 40, "is_lab": True, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000013"), "name": "EC Lab 1", "capacity": 40, "is_lab": True, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000014"), "name": "EC Lab 2", "capacity": 40, "is_lab": True, "is_active": True},
        {"id": uuid.UUID("50000000-0000-0000-0000-000000000015"), "name": "ME Workshop", "capacity": 40, "is_lab": True, "is_active": True},
    ]
    stmt = pg_insert(Room).values(rooms).on_conflict_do_nothing(index_elements=["name"])
    db.execute(stmt)
    db.flush()
    actual = db.execute(text("SELECT id, name FROM room")).fetchall()
    return {row.name: row.id for row in actual}


def seed_periods(db: Session) -> dict[tuple[int, str], uuid.UUID]:
    """
    Seed 30 periods: 6 time slots × 5 weekdays (Mon-Fri).
    Returns {(weekday, label): id}.
    """
    time_slots = [
        ("P1", time(9, 0),  time(10, 0)),
        ("P2", time(10, 0), time(11, 0)),
        ("P3", time(11, 15), time(12, 15)),
        ("P4", time(12, 15), time(13, 15)),
        ("P5", time(14, 0), time(15, 0)),
        ("P6", time(15, 0), time(16, 0)),
    ]
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    rows = []
    period_map: dict[tuple[int, str], uuid.UUID] = {}

    for wd in range(5):
        for label, start, end in time_slots:
            pid = _rng_uuid()
            rows.append({
                "id": pid,
                "weekday": wd,
                "start_time": start,
                "end_time": end,
                "label": label,
            })
            period_map[(wd, label)] = pid

    stmt = pg_insert(Period).values(rows).on_conflict_do_nothing(
        index_elements=["weekday", "start_time"]
    )
    db.execute(stmt)
    db.flush()

    # Re-read from DB to get actual IDs (handles idempotent re-runs)
    actual = db.execute(
        text("SELECT id, weekday, label FROM period ORDER BY weekday, start_time")
    ).fetchall()
    period_map = {(row.weekday, row.label): row.id for row in actual}
    return period_map


def seed_faculty(db: Session, dept_ids: dict[str, uuid.UUID]) -> dict[str, dict]:
    """
    Seed 30 faculty (10 per department). Returns {employee_code: {id, dept, ...}}.
    Key entries use fixed UUIDs; others use seeded RNG.
    """
    NEHA_GUPTA_ID  = uuid.UUID("30000000-0000-0000-0000-000000000008")

    faculty_data = [
        # ── CS Department ─────────────────────────────────────────────────
        {"id": SHARMA_ID,       "code": "CS001", "name": "Dr. Raj Sharma",      "dept": "CS", "max_h": 20.0},
        {"id": _rng_uuid(),     "code": "CS002", "name": "Dr. Priya Patel",     "dept": "CS", "max_h": 20.0},
        {"id": ARUN_KUMAR_ID,   "code": "CS003", "name": "Dr. Arun Kumar",      "dept": "CS", "max_h": 20.0},
        {"id": _rng_uuid(),     "code": "CS004", "name": "Dr. Sunita Mehta",    "dept": "CS", "max_h": 18.0},
        {"id": _rng_uuid(),     "code": "CS005", "name": "Dr. Vikram Singh",    "dept": "CS", "max_h": 20.0},
        {"id": _rng_uuid(),     "code": "CS006", "name": "Dr. Kavitha Rao",     "dept": "CS", "max_h": 20.0},
        {"id": _rng_uuid(),     "code": "CS007", "name": "Dr. Amit Joshi",      "dept": "CS", "max_h": 20.0},
        {"id": NEHA_GUPTA_ID,   "code": "CS008", "name": "Dr. Neha Gupta",      "dept": "CS", "max_h": 20.0},
        {"id": SANJAY_VERMA_ID, "code": "CS009", "name": "Dr. Sanjay Verma",   "dept": "CS", "max_h": 20.0},
        {"id": _rng_uuid(),     "code": "CS010", "name": "Dr. Lalitha Nair",    "dept": "CS", "max_h": 18.0},
        # ── EC Department ─────────────────────────────────────────────────
        {"id": _rng_uuid(), "code": "EC001", "name": "Dr. Ramesh Iyer",        "dept": "EC", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "EC002", "name": "Dr. Deepa Krishnan",     "dept": "EC", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "EC003", "name": "Dr. Suresh Bhat",        "dept": "EC", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "EC004", "name": "Dr. Ananya Roy",         "dept": "EC", "max_h": 18.0},
        {"id": _rng_uuid(), "code": "EC005", "name": "Dr. Mohan Pillai",       "dept": "EC", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "EC006", "name": "Dr. Vani Subramanian",   "dept": "EC", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "EC007", "name": "Dr. Kiran Desai",        "dept": "EC", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "EC008", "name": "Dr. Padma Nair",         "dept": "EC", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "EC009", "name": "Dr. Ravi Menon",         "dept": "EC", "max_h": 18.0},
        {"id": _rng_uuid(), "code": "EC010", "name": "Dr. Usha Shetty",        "dept": "EC", "max_h": 20.0},
        # ── ME Department ─────────────────────────────────────────────────
        {"id": _rng_uuid(), "code": "ME001", "name": "Dr. Prakash Yadav",      "dept": "ME", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "ME002", "name": "Dr. Geeta Shastri",      "dept": "ME", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "ME003", "name": "Dr. Arjun Nayak",        "dept": "ME", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "ME004", "name": "Dr. Laxmi Bhatt",        "dept": "ME", "max_h": 18.0},
        {"id": _rng_uuid(), "code": "ME005", "name": "Dr. Manoj Tiwari",       "dept": "ME", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "ME006", "name": "Dr. Rekha Pandey",       "dept": "ME", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "ME007", "name": "Dr. Satish Reddy",       "dept": "ME", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "ME008", "name": "Dr. Kavya Narayan",      "dept": "ME", "max_h": 20.0},
        {"id": _rng_uuid(), "code": "ME009", "name": "Dr. Harish Jain",        "dept": "ME", "max_h": 18.0},
        {"id": _rng_uuid(), "code": "ME010", "name": "Dr. Meena Kulkarni",     "dept": "ME", "max_h": 20.0},
    ]
    rows = [
        {
            "id": f["id"],
            "name": f["name"],
            "employee_code": f["code"],
            "department_id": dept_ids[f["dept"]],
            "weekly_max_hours": f["max_h"],
            "is_active": True,
        }
        for f in faculty_data
    ]
    stmt = pg_insert(Faculty).values(rows).on_conflict_do_nothing(index_elements=["employee_code"])
    db.execute(stmt)
    db.flush()
    actual = db.execute(text("SELECT id, employee_code, name FROM faculty")).fetchall()
    dept_by_code = {f["code"]: f["dept"] for f in faculty_data}
    return {
        row.employee_code: {
            "id": row.id,
            "dept": dept_by_code.get(row.employee_code, "CS"),
            "name": row.name,
        }
        for row in actual
    }


def seed_faculty_expertise(db: Session, faculty_map: dict[str, dict]) -> None:
    """Seed 2-3 expertise tags per faculty member."""
    expertise_data: list[tuple[str, str, str]] = [
        # (employee_code, course_tag, level)
        # CS faculty
        ("CS001", "data_structures", "primary"),
        ("CS001", "algorithms",      "primary"),
        ("CS001", "programming",     "secondary"),
        ("CS002", "databases",       "primary"),
        ("CS002", "data_mining",     "primary"),
        ("CS002", "programming",     "secondary"),
        ("CS003", "operating_systems",   "primary"),
        ("CS003", "computer_networks",   "primary"),
        ("CS003", "programming",         "secondary"),
        ("CS004", "software_engineering","primary"),
        ("CS004", "agile",               "primary"),
        ("CS004", "web_technologies",    "secondary"),
        ("CS005", "machine_learning",    "primary"),
        ("CS005", "ai",                  "primary"),
        ("CS005", "algorithms",          "secondary"),
        ("CS006", "computer_graphics",   "primary"),
        ("CS006", "hci",                 "primary"),
        ("CS006", "web_technologies",    "secondary"),
        ("CS007", "theory_of_computation","primary"),
        ("CS007", "compilers",            "primary"),
        ("CS007", "algorithms",           "secondary"),
        ("CS008", "web_technologies",     "primary"),
        ("CS008", "mobile_computing",     "primary"),
        ("CS008", "databases",            "secondary"),
        ("CS009", "data_structures",      "primary"),
        ("CS009", "programming",          "primary"),
        # Note: CS009 (Sanjay Verma) deliberately has NO machine_learning expertise
        # This plants HC-06 when he's assigned CS301.
        ("CS010", "mathematics",          "primary"),
        ("CS010", "discrete_math",        "primary"),
        ("CS010", "theory_of_computation","secondary"),
        # EC faculty
        ("EC001", "analog_circuits",      "primary"),
        ("EC001", "vlsi",                 "secondary"),
        ("EC002", "digital_electronics",  "primary"),
        ("EC002", "microprocessors",      "primary"),
        ("EC003", "signal_processing",    "primary"),
        ("EC003", "communications",       "primary"),
        ("EC004", "embedded_systems",     "primary"),
        ("EC004", "iot",                  "primary"),
        ("EC005", "control_systems",      "primary"),
        ("EC005", "robotics",             "secondary"),
        ("EC006", "fiber_optics",         "primary"),
        ("EC006", "photonics",            "primary"),
        ("EC007", "wireless_communications","primary"),
        ("EC007", "antennas",              "primary"),
        ("EC008", "vlsi",                  "primary"),
        ("EC008", "asic_design",           "primary"),
        ("EC009", "power_electronics",     "primary"),
        ("EC009", "drives",               "primary"),
        ("EC010", "biomedical_electronics","primary"),
        ("EC010", "sensors",              "primary"),
        # ME faculty
        ("ME001", "thermodynamics",        "primary"),
        ("ME001", "heat_transfer",         "primary"),
        ("ME002", "manufacturing",         "primary"),
        ("ME002", "metrology",             "primary"),
        ("ME003", "machine_design",        "primary"),
        ("ME003", "strength_of_materials", "primary"),
        ("ME004", "fluid_mechanics",       "primary"),
        ("ME004", "turbomachinery",        "secondary"),
        ("ME005", "cad",                   "primary"),
        ("ME005", "cam",                   "primary"),
        ("ME006", "materials_science",     "primary"),
        ("ME006", "metallurgy",            "primary"),
        ("ME007", "industrial_engineering","primary"),
        ("ME007", "operations_research",   "primary"),
        ("ME008", "ic_engines",            "primary"),
        ("ME008", "automobile_engineering","secondary"),
        ("ME009", "robotics",              "primary"),
        ("ME009", "automation",            "primary"),
        ("ME010", "composite_materials",   "primary"),
        ("ME010", "nanotech",              "secondary"),
    ]
    rows = [
        {
            "id": _rng_uuid(),
            "faculty_id": faculty_map[code]["id"],
            "course_tag": tag,
            "level": ExpertiseLevelEnum(level),
        }
        for code, tag, level in expertise_data
    ]
    stmt = pg_insert(FacultyExpertise).values(rows).on_conflict_do_nothing(
        index_elements=["faculty_id", "course_tag"]
    )
    db.execute(stmt)
    db.flush()


def seed_courses(db: Session, dept_ids: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    """Seed 40 courses (14 CS, 13 EC, 13 ME). Returns {code: id}."""
    courses = [
        # CS
        {"code": "CS101", "name": "Data Structures",               "dept": "CS", "lab": False, "exp": "data_structures"},
        {"code": "CS102", "name": "Programming in C",              "dept": "CS", "lab": False, "exp": "programming"},
        {"code": "CS201", "name": "Algorithms",                    "dept": "CS", "lab": False, "exp": "algorithms"},
        {"code": "CS202", "name": "Database Management Systems",   "dept": "CS", "lab": False, "exp": "databases"},
        {"code": "CS203", "name": "Operating Systems",             "dept": "CS", "lab": False, "exp": "operating_systems"},
        {"code": "CS204", "name": "Computer Networks",             "dept": "CS", "lab": False, "exp": "computer_networks"},
        {"code": "CS205", "name": "Software Engineering",          "dept": "CS", "lab": False, "exp": "software_engineering"},
        {"code": "CS301", "name": "Machine Learning",              "dept": "CS", "lab": False, "exp": "machine_learning"},
        {"code": "CS302", "name": "Web Technologies",              "dept": "CS", "lab": True,  "exp": "web_technologies"},
        {"code": "CS303", "name": "Theory of Computation",         "dept": "CS", "lab": False, "exp": "theory_of_computation"},
        {"code": "CS304", "name": "Compiler Design",               "dept": "CS", "lab": False, "exp": "compilers"},
        {"code": "CS305", "name": "Computer Graphics",             "dept": "CS", "lab": True,  "exp": "computer_graphics"},
        {"code": "CS401", "name": "Artificial Intelligence",       "dept": "CS", "lab": False, "exp": "ai"},
        {"code": "CS402", "name": "Mobile Computing",              "dept": "CS", "lab": True,  "exp": "mobile_computing"},
        # EC
        {"code": "EC101", "name": "Basic Electronics",             "dept": "EC", "lab": False, "exp": "analog_circuits"},
        {"code": "EC102", "name": "Digital Electronics",           "dept": "EC", "lab": False, "exp": "digital_electronics"},
        {"code": "EC201", "name": "Analog Circuits",               "dept": "EC", "lab": True,  "exp": "analog_circuits"},
        {"code": "EC202", "name": "Signal Processing",             "dept": "EC", "lab": False, "exp": "signal_processing"},
        {"code": "EC203", "name": "Microprocessors & MCUs",        "dept": "EC", "lab": True,  "exp": "microprocessors"},
        {"code": "EC204", "name": "Communications Engineering",    "dept": "EC", "lab": False, "exp": "communications"},
        {"code": "EC205", "name": "VLSI Design",                   "dept": "EC", "lab": True,  "exp": "vlsi"},
        {"code": "EC301", "name": "Embedded Systems",              "dept": "EC", "lab": True,  "exp": "embedded_systems"},
        {"code": "EC302", "name": "Wireless Communications",       "dept": "EC", "lab": False, "exp": "wireless_communications"},
        {"code": "EC303", "name": "Control Systems",               "dept": "EC", "lab": False, "exp": "control_systems"},
        {"code": "EC304", "name": "Fiber Optics",                  "dept": "EC", "lab": False, "exp": "fiber_optics"},
        {"code": "EC401", "name": "IoT Systems",                   "dept": "EC", "lab": True,  "exp": "iot"},
        {"code": "EC402", "name": "Power Electronics",             "dept": "EC", "lab": False, "exp": "power_electronics"},
        # ME
        {"code": "ME101", "name": "Engineering Mathematics",       "dept": "ME", "lab": False, "exp": None},
        {"code": "ME102", "name": "Engineering Drawing",           "dept": "ME", "lab": True,  "exp": "cad"},
        {"code": "ME201", "name": "Thermodynamics",                "dept": "ME", "lab": False, "exp": "thermodynamics"},
        {"code": "ME202", "name": "Fluid Mechanics",               "dept": "ME", "lab": False, "exp": "fluid_mechanics"},
        {"code": "ME203", "name": "Strength of Materials",         "dept": "ME", "lab": False, "exp": "strength_of_materials"},
        {"code": "ME204", "name": "Manufacturing Technology",      "dept": "ME", "lab": True,  "exp": "manufacturing"},
        {"code": "ME205", "name": "Machine Design",                "dept": "ME", "lab": False, "exp": "machine_design"},
        {"code": "ME301", "name": "Heat Transfer",                 "dept": "ME", "lab": False, "exp": "heat_transfer"},
        {"code": "ME302", "name": "CAD/CAM",                       "dept": "ME", "lab": True,  "exp": "cad"},
        {"code": "ME303", "name": "Industrial Engineering",        "dept": "ME", "lab": False, "exp": "industrial_engineering"},
        {"code": "ME304", "name": "Materials Science",             "dept": "ME", "lab": False, "exp": "materials_science"},
        {"code": "ME401", "name": "Robotics & Automation",         "dept": "ME", "lab": True,  "exp": "robotics"},
        {"code": "ME402", "name": "IC Engines",                    "dept": "ME", "lab": False, "exp": "ic_engines"},
    ]
    rows = [
        {
            "id": _rng_uuid(),
            "code": c["code"],
            "name": c["name"],
            "department_id": dept_ids[c["dept"]],
            "requires_lab": c["lab"],
            "required_expertise_tag": c["exp"],
        }
        for c in courses
    ]
    stmt = pg_insert(Course).values(rows).on_conflict_do_nothing(index_elements=["code"])
    db.execute(stmt)
    db.flush()

    # Re-read actual IDs (idempotent)
    actual = db.execute(text("SELECT id, code FROM course")).fetchall()
    return {row.code: row.id for row in actual}


def seed_sections(db: Session, dept_ids: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    """Seed 12 sections (4 per department, years 1-4). Returns {name: id}."""
    sections = [
        # CS
        {"name": "CS-1A", "dept": "CS", "enrollment": 65, "year": 1},
        {"name": "CS-2A", "dept": "CS", "enrollment": 58, "year": 2},
        {"name": "CS-3A", "dept": "CS", "enrollment": 52, "year": 3},
        {"name": "CS-4A", "dept": "CS", "enrollment": 45, "year": 4},
        # EC
        {"name": "EC-1A", "dept": "EC", "enrollment": 60, "year": 1},
        {"name": "EC-2A", "dept": "EC", "enrollment": 55, "year": 2},
        {"name": "EC-3A", "dept": "EC", "enrollment": 48, "year": 3},
        {"name": "EC-4A", "dept": "EC", "enrollment": 40, "year": 4},
        # ME
        {"name": "ME-1A", "dept": "ME", "enrollment": 58, "year": 1},
        {"name": "ME-2A", "dept": "ME", "enrollment": 52, "year": 2},
        {"name": "ME-3A", "dept": "ME", "enrollment": 45, "year": 3},
        {"name": "ME-4A", "dept": "ME", "enrollment": 38, "year": 4},
    ]
    rows = [
        {
            "id": _rng_uuid(),
            "name": s["name"],
            "department_id": dept_ids[s["dept"]],
            "enrollment": s["enrollment"],
            "year_of_study": s["year"],
        }
        for s in sections
    ]
    stmt = pg_insert(Section).values(rows).on_conflict_do_nothing()
    db.execute(stmt)
    db.flush()

    actual = db.execute(text("SELECT id, name FROM section")).fetchall()
    return {row.name: row.id for row in actual}


def seed_timetable_entries(
    db: Session,
    faculty_map: dict[str, dict],
    section_map: dict[str, uuid.UUID],
    course_map: dict[str, uuid.UUID],
    room_map: dict[str, uuid.UUID],
    period_map: dict[tuple[int, str], uuid.UUID],
) -> None:
    """
    Seed timetable entries.

    Strategy:
    1. Insert explicitly defined hero-scenario entries for Dr. Sharma.
    2. Insert 5 deliberately planted violations (HC-01 through HC-06).
    3. Insert additional entries for other faculty using RNG (conflict-safe).

    Weekday encoding: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri.
    """
    # Tracking dicts to prevent accidental conflicts in the random section.
    # Planted conflicts are inserted first and NOT tracked here.
    faculty_busy: dict[tuple, bool] = {}    # (faculty_id, period_id)
    room_busy: dict[tuple, bool] = {}       # (room_id, period_id)
    section_used: dict[tuple, bool] = {}    # (section_id, period_id)

    def try_add(section: str, course: str, faculty_code: str, room: str, weekday: int, period_label: str) -> dict | None:
        """Build a timetable row, checking for accidental conflicts."""
        sid = section_map.get(section)
        cid = course_map.get(course)
        fid = faculty_map.get(faculty_code, {}).get("id")
        rid = room_map.get(room)
        pid = period_map.get((weekday, period_label))
        if None in (sid, cid, fid, rid, pid):
            logger.warning(f"Skipping entry: missing entity {section} {course} {faculty_code} {room} {weekday} {period_label}")
            return None
        if section_used.get((sid, pid)):
            return None
        if faculty_busy.get((fid, pid)):
            return None
        if room_busy.get((rid, pid)):
            return None
        section_used[(sid, pid)] = True
        faculty_busy[(fid, pid)] = True
        room_busy[(rid, pid)] = True
        return {
            "id": _rng_uuid(),
            "section_id": sid,
            "course_id": cid,
            "faculty_id": fid,
            "room_id": rid,
            "period_id": pid,
        }

    entries: list[dict] = []

    # ── Hero scenario: Dr. Raj Sharma (CS001) ─────────────────────────────
    # Leave: 2026-11-02 (Mon) to 2026-11-04 (Wed)
    # Affected: Mon P2, Mon P4, Tue P1, Tue P3, Wed P1, Wed P2
    hero_entries = [
        # section,  course,  faculty,  room,       wd, period
        ("CS-3A", "CS201", "CS001", "Room 201",  0, "P2"),  # Mon P2 ← affected
        ("CS-2A", "CS101", "CS001", "Room 101",  0, "P4"),  # Mon P4 ← affected
        ("CS-2A", "CS101", "CS001", "Room 101",  1, "P1"),  # Tue P1 ← affected
        ("CS-4A", "CS201", "CS001", "Room 201",  1, "P3"),  # Tue P3 ← affected
        ("CS-1A", "CS102", "CS001", "Room 101",  2, "P1"),  # Wed P1 ← affected
        ("CS-3A", "CS201", "CS001", "Room 201",  2, "P2"),  # Wed P2 ← affected
        ("CS-4A", "CS101", "CS001", "Room 101",  4, "P1"),  # Fri P1 — NOT affected
    ]
    for args in hero_entries:
        row = try_add(*args)
        if row:
            entries.append(row)

    # ── Planted HC-01: Dr. Arun Kumar (CS003) double-booked Mon P1 ────────
    # Both entries have the same (faculty_id, period_id) → HC-01 violation.
    # Inserted DIRECTLY without using try_add (which would block the second).
    hc01_pid = period_map[(0, "P1")]  # Mon P1
    hc01_fid = faculty_map["CS003"]["id"]
    hc01_entries = [
        {   # CS-1A, CS203, Arun Kumar, Room 101, Mon P1
            "id": _rng_uuid(),
            "section_id": section_map["CS-1A"],
            "course_id": course_map["CS203"],
            "faculty_id": hc01_fid,
            "room_id": room_map["Room 101"],
            "period_id": hc01_pid,
        },
        {   # CS-2A, CS204, Arun Kumar, Room 102, Mon P1 ← SAME faculty+period → HC-01
            "id": _rng_uuid(),
            "section_id": section_map["CS-2A"],
            "course_id": course_map["CS204"],
            "faculty_id": hc01_fid,
            "room_id": room_map["Room 102"],
            "period_id": hc01_pid,
        },
    ]
    entries.extend(hc01_entries)
    # Mark CS-1A and CS-2A as used at Mon P1 (so random section doesn't re-use)
    section_used[(section_map["CS-1A"], hc01_pid)] = True
    section_used[(section_map["CS-2A"], hc01_pid)] = True
    # Do NOT mark faculty as busy — the HC-01 is the point

    # ── Planted HC-02: Room 301 double-booked Tue P3 ──────────────────────
    hc02_pid = period_map[(1, "P3")]  # Tue P3
    hc02_entries = [
        {   # EC-1A, EC101, EC001, Room 301, Tue P3
            "id": _rng_uuid(),
            "section_id": section_map["EC-1A"],
            "course_id": course_map["EC101"],
            "faculty_id": faculty_map["EC001"]["id"],
            "room_id": ROOM_301_ID,
            "period_id": hc02_pid,
        },
        {   # ME-1A, ME101, ME001, Room 301, Tue P3 ← SAME room+period → HC-02
            "id": _rng_uuid(),
            "section_id": section_map["ME-1A"],
            "course_id": course_map["ME101"],
            "faculty_id": faculty_map["ME001"]["id"],
            "room_id": ROOM_301_ID,
            "period_id": hc02_pid,
        },
    ]
    entries.extend(hc02_entries)
    section_used[(section_map["EC-1A"], hc02_pid)] = True
    section_used[(section_map["ME-1A"], hc02_pid)] = True

    # ── Planted HC-04: CS-1A (enrollment=65) in Room 101 (capacity=60) Thu P1
    hc04_pid = period_map[(3, "P1")]  # Thu P1
    entries.append({
        "id": _rng_uuid(),
        "section_id": section_map["CS-1A"],
        "course_id": course_map["CS102"],
        "faculty_id": faculty_map["CS009"]["id"],  # Sanjay Verma (has programming expertise)
        "room_id": ROOM_101_ID,                    # capacity=60, enrollment=65 → HC-04
        "period_id": hc04_pid,
    })
    section_used[(section_map["CS-1A"], hc04_pid)] = True
    faculty_busy[(faculty_map["CS009"]["id"], hc04_pid)] = True
    room_busy[(ROOM_101_ID, hc04_pid)] = True

    # ── Planted HC-05: CS402 (requires_lab=True) in Room 101 (not a lab) Fri P5
    hc05_pid = period_map[(4, "P5")]  # Fri P5
    entries.append({
        "id": _rng_uuid(),
        "section_id": section_map["CS-4A"],
        "course_id": course_map["CS402"],           # requires_lab=True
        "faculty_id": faculty_map["CS008"]["id"],   # Neha Gupta (mobile_computing expertise ✓)
        "room_id": ROOM_101_ID,                     # is_lab=False → HC-05
        "period_id": hc05_pid,
    })
    section_used[(section_map["CS-4A"], hc05_pid)] = True
    faculty_busy[(faculty_map["CS008"]["id"], hc05_pid)] = True
    room_busy[(ROOM_101_ID, hc05_pid)] = True

    # ── Planted HC-06: CS301 ML — Sanjay Verma has NO machine_learning expertise
    hc06_pid = period_map[(4, "P6")]  # Fri P6
    entries.append({
        "id": _rng_uuid(),
        "section_id": section_map["CS-4A"],
        "course_id": course_map["CS301"],           # required_expertise_tag=machine_learning
        "faculty_id": faculty_map["CS009"]["id"],   # Sanjay Verma — no ML expertise → HC-06
        "room_id": room_map["Room 201"],
        "period_id": hc06_pid,
    })
    section_used[(section_map["CS-4A"], hc06_pid)] = True
    faculty_busy[(faculty_map["CS009"]["id"], hc06_pid)] = True

    # ── Additional entries (RNG, conflict-safe) ───────────────────────────
    extra = [
        # CS faculty covering their courses
        ("CS-1A", "CS203", "CS003", "Room 103",   0, "P2"),  # Arun Kumar Mon P2
        ("CS-2A", "CS202", "CS002", "Room 102",   0, "P3"),  # Priya DB Mon P3
        ("CS-3A", "CS205", "CS004", "Room 201",   0, "P1"),  # Sunita SE Mon P1
        ("CS-3A", "CS205", "CS004", "Room 201",   2, "P3"),  # Sunita SE Wed P3
        ("CS-4A", "CS401", "CS005", "Room 202",   0, "P1"),  # Vikram AI Mon P1
        ("CS-4A", "CS401", "CS005", "Room 202",   2, "P1"),  # Vikram AI Wed P1
        ("CS-1A", "CS102", "CS001", "Room 101",   3, "P2"),  # Sharma Thu P2 (not on leave)
        ("CS-2A", "CS303", "CS007", "Room 102",   3, "P3"),  # Amit TOC Thu P3
        ("CS-3A", "CS304", "CS007", "Room 201",   3, "P1"),  # Amit Compilers Thu P1
        ("CS-3A", "CS302", "CS008", "CS Lab 1",   4, "P2"),  # Neha Web Fri P2
        ("CS-1A", "CS101", "CS001", "Room 101",   4, "P3"),  # Sharma DS Fri P3
        ("CS-2A", "CS204", "CS003", "Room 102",   1, "P2"),  # Arun CN Tue P2
        ("CS-3A", "CS202", "CS002", "Room 201",   1, "P4"),  # Priya DB Tue P4
        ("CS-2A", "CS205", "CS004", "Room 102",   3, "P4"),  # Sunita SE Thu P4
        # EC faculty
        ("EC-2A", "EC202", "EC003", "Seminar Hall A", 0, "P1"),
        ("EC-2A", "EC202", "EC003", "Seminar Hall A", 2, "P1"),
        ("EC-3A", "EC303", "EC005", "Room 302",    0, "P3"),
        ("EC-3A", "EC303", "EC005", "Room 302",    2, "P3"),
        ("EC-4A", "EC401", "EC004", "EC Lab 1",    1, "P1"),
        ("EC-4A", "EC401", "EC004", "EC Lab 1",    3, "P1"),
        ("EC-2A", "EC205", "EC008", "EC Lab 2",    0, "P2"),
        ("EC-2A", "EC205", "EC008", "EC Lab 2",    2, "P2"),
        ("EC-1A", "EC102", "EC002", "Room 301",    0, "P1"),
        ("EC-3A", "EC302", "EC007", "Room 302",    1, "P1"),
        ("EC-4A", "EC402", "EC009", "Room 302",    1, "P2"),
        ("EC-4A", "EC402", "EC009", "Room 302",    3, "P2"),
        ("EC-1A", "EC204", "EC003", "Seminar Hall A", 4, "P1"),
        # ME faculty
        ("ME-1A", "ME201", "ME001", "Room 102",    0, "P3"),
        ("ME-1A", "ME201", "ME001", "Room 102",    2, "P3"),
        ("ME-2A", "ME202", "ME004", "Room 103",    0, "P1"),
        ("ME-2A", "ME202", "ME004", "Room 103",    2, "P1"),
        ("ME-3A", "ME205", "ME003", "Room 203",    0, "P2"),
        ("ME-3A", "ME205", "ME003", "Room 203",    2, "P2"),
        ("ME-4A", "ME401", "ME009", "ME Workshop",  1, "P4"),
        ("ME-4A", "ME401", "ME009", "ME Workshop",  3, "P4"),
        ("ME-2A", "ME204", "ME002", "ME Workshop",  0, "P4"),
        ("ME-2A", "ME204", "ME002", "ME Workshop",  2, "P4"),
        ("ME-1A", "ME102", "ME005", "ME Workshop",  4, "P3"),
        ("ME-3A", "ME303", "ME007", "Room 302",    3, "P3"),
        ("ME-4A", "ME402", "ME008", "Seminar Hall B", 4, "P2"),
        ("ME-2A", "ME203", "ME003", "Room 103",    3, "P2"),
        ("ME-3A", "ME301", "ME001", "Room 102",    4, "P1"),
        ("ME-4A", "ME304", "ME006", "Room 203",    0, "P3"),
    ]
    for args in extra:
        row = try_add(*args)
        if row:
            entries.append(row)

    stmt = pg_insert(TimetableEntry).values(entries).on_conflict_do_nothing(
        index_elements=["section_id", "period_id"]
    )
    db.execute(stmt)
    db.flush()
    logger.info(f"Inserted {len(entries)} timetable entries")


def seed_faculty_leaves(db: Session, faculty_map: dict[str, dict]) -> None:
    """
    Seed faculty leave records.

    Hero scenario: Dr. Raj Sharma on leave 2026-11-02 (Mon) to 2026-11-04 (Wed).
    Additional leaves add variety for dashboard and evaluation.
    """
    leaves = [
        # (id, faculty_code, start_date, end_date, reason)
        # Hero scenario leave — fixed ID for stable references
        (HERO_LEAVE_ID, "CS001", date(2026, 11, 2), date(2026, 11, 4), "Medical leave"),
        # Additional leaves
        (_rng_uuid(), "EC003", date(2026, 10, 28), date(2026, 10, 28), "Conference attendance"),
        (_rng_uuid(), "ME001", date(2026, 11, 9),  date(2026, 11, 11), "Family emergency"),
        (_rng_uuid(), "CS005", date(2026, 10, 30), date(2026, 10, 30), "Workshop"),
        (_rng_uuid(), "EC007", date(2026, 11, 16), date(2026, 11, 20), "Academic leave"),
        (_rng_uuid(), "ME004", date(2026, 10, 26), date(2026, 10, 26), "Medical appointment"),
    ]
    rows = [
        {
            "id": lid,
            "faculty_id": faculty_map[code]["id"],
            "start_date": start,
            "end_date": end,
            "reason": reason,
        }
        for lid, code, start, end, reason in leaves
    ]
    stmt = pg_insert(FacultyLeave).values(rows).on_conflict_do_nothing(index_elements=["id"])
    db.execute(stmt)
    db.flush()


def seed_class_occurrences(db: Session) -> int:
    """
    Pre-generate class_occurrence rows for all timetable_entries within
    the 6-week window [OCCURRENCE_WINDOW_START, OCCURRENCE_WINDOW_END].

    Uses ON CONFLICT DO NOTHING to be idempotent — safe to run multiple times.
    Returns number of newly created rows.

    Leave-date boundary test data:
    - Window starts 2026-10-19 and includes leave boundaries at 2026-11-02 and 2026-11-04.
    - Occurrences exist for BOTH the day before and day after the leave period.
    """
    # Load all timetable entries with their period weekdays
    rows_q = db.execute(
        text("""
            SELECT te.id AS entry_id, p.weekday
            FROM timetable_entry te
            JOIN period p ON te.period_id = p.id
        """)
    ).fetchall()

    occurrence_rows: list[dict] = []
    for row in rows_q:
        matching_dates = dates_for_weekday_in_range(
            row.weekday, OCCURRENCE_WINDOW_START, OCCURRENCE_WINDOW_END
        )
        for d in matching_dates:
            occurrence_rows.append({
                "id": _rng_uuid(),
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
    created = result.rowcount if result.rowcount >= 0 else len(occurrence_rows)
    logger.info(f"Generated {created} class occurrences (window {OCCURRENCE_WINDOW_START} to {OCCURRENCE_WINDOW_END})")
    return created


# ── Main entry point ──────────────────────────────────────────────────────


def run_seed(db: Session) -> None:
    """Execute all seed steps in dependency order."""
    logger.info("=== Campus OS Seed — SYNTHETIC DATA ONLY ===")

    dept_ids = seed_departments(db)
    logger.info(f"Departments: {list(dept_ids.keys())}")

    seed_users(db, dept_ids)
    logger.info("Demo users seeded")

    room_map = seed_rooms(db)
    logger.info(f"Rooms: {len(room_map)}")

    period_map = seed_periods(db)
    logger.info(f"Periods: {len(period_map)}")

    faculty_map = seed_faculty(db, dept_ids)
    logger.info(f"Faculty: {len(faculty_map)}")

    seed_faculty_expertise(db, faculty_map)
    logger.info("Faculty expertise seeded")

    course_map = seed_courses(db, dept_ids)
    logger.info(f"Courses: {len(course_map)}")

    section_map = seed_sections(db, dept_ids)
    logger.info(f"Sections: {len(section_map)}")

    seed_timetable_entries(db, faculty_map, section_map, course_map, room_map, period_map)
    logger.info("Timetable entries seeded (including 5 planted violations)")

    seed_faculty_leaves(db, faculty_map)
    logger.info("Faculty leaves seeded (including hero scenario leave)")

    db.commit()
    logger.info("Core seed committed")

    n = seed_class_occurrences(db)
    logger.info(f"Class occurrences seeded: {n} new rows")
    logger.info("=== Seed complete ===")


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Campus OS data seed")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before seeding")
    args = parser.parse_args()

    if args.reset:
        logger.warning("--reset specified: dropping all tables and recreating from scratch")
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    with SessionLocal() as db:
        run_seed(db)


if __name__ == "__main__":
    main()
