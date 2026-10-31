"""
SQLAlchemy ORM models for Campus OS.

Design notes
------------
* All PKs are UUID (gen_random_uuid via Python default).
* Dates: stored as DATE (no timezone) — institution timezone is Asia/Kolkata,
  documented as a fixed prototype assumption.
* Times: stored as TIME (no timezone) — local wall-clock time.
* timetable_entry is the RECURRING weekly template.
* class_occurrence is a SPECIFIC dated instance of a timetable_entry.
  Replacements are recorded on class_occurrence, never on timetable_entry.
* Unique constraints on timetable_entry:
    (section_id, period_id) — enforced in DB.
    (faculty_id, period_id) and (room_id, period_id) are intentionally NOT
    unique at DB level so the seed script can plant deliberate conflicts
    for the rule engine (M2) to detect.
* SYNTHETIC DATA LABEL: all seeded data is synthetic and clearly labeled.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


# ── Enum definitions ──────────────────────────────────────────────────────


class RoleEnum(str, enum.Enum):
    principal = "principal"
    hod = "hod"
    exam_cell = "exam_cell"


class ExpertiseLevelEnum(str, enum.Enum):
    primary = "primary"
    secondary = "secondary"


class OccurrenceStatusEnum(str, enum.Enum):
    scheduled = "scheduled"
    cancelled = "cancelled"
    covered = "covered"


class DecisionStatusEnum(str, enum.Enum):
    simulation = "simulation"
    approved = "approved"
    rejected = "rejected"


# ── Base ──────────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


# ── Organizational ────────────────────────────────────────────────────────


class Department(Base):
    __tablename__ = "department"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    users = relationship("User", back_populates="department")
    faculty = relationship("Faculty", back_populates="department")
    courses = relationship("Course", back_populates="department")
    sections = relationship("Section", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department {self.code}>"


class User(Base):
    __tablename__ = "user"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(254), unique=True, nullable=False, index=True)
    hashed_password = Column(String(200), nullable=False)
    role = Column(SAEnum(RoleEnum, name="roleenum"), nullable=False)
    # Principal: department_id is NULL (institution-wide access)
    # HOD / Exam Cell: must reference their department
    department_id = Column(PGUUID(as_uuid=True), ForeignKey("department.id", ondelete="RESTRICT"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    department = relationship("Department", back_populates="users")
    decisions = relationship("Decision", back_populates="created_by_user")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


# ── Faculty ───────────────────────────────────────────────────────────────


class Faculty(Base):
    __tablename__ = "faculty"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    employee_code = Column(String(50), unique=True, nullable=False)
    department_id = Column(PGUUID(as_uuid=True), ForeignKey("department.id", ondelete="RESTRICT"), nullable=False)
    # weekly_max_hours: hard cap for HC-07.  Calculated as the SUM of
    # period durations (end_time - start_time in hours) across the Mon-Sun week.
    weekly_max_hours = Column(Float, nullable=False, default=20.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    department = relationship("Department", back_populates="faculty")
    expertise = relationship("FacultyExpertise", back_populates="faculty", cascade="all, delete-orphan")
    leaves = relationship("FacultyLeave", back_populates="faculty", cascade="all, delete-orphan")
    timetable_entries = relationship("TimetableEntry", back_populates="faculty", foreign_keys="TimetableEntry.faculty_id")
    override_occurrences = relationship("ClassOccurrence", back_populates="override_faculty", foreign_keys="ClassOccurrence.override_faculty_id")

    def __repr__(self) -> str:
        return f"<Faculty {self.employee_code} {self.name}>"


class FacultyExpertise(Base):
    __tablename__ = "faculty_expertise"
    __table_args__ = (UniqueConstraint("faculty_id", "course_tag", name="uq_faculty_expertise"),)

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_id = Column(PGUUID(as_uuid=True), ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False)
    course_tag = Column(String(100), nullable=False)
    level = Column(SAEnum(ExpertiseLevelEnum, name="expertiselevelenum"), nullable=False)

    faculty = relationship("Faculty", back_populates="expertise")

    def __repr__(self) -> str:
        return f"<FacultyExpertise {self.course_tag} ({self.level})>"


class FacultyLeave(Base):
    __tablename__ = "faculty_leave"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    faculty_id = Column(PGUUID(as_uuid=True), ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_leave_dates"),
    )

    faculty = relationship("Faculty", back_populates="leaves")

    def covers_date(self, d: date) -> bool:
        """Return True if leave applies on date d (inclusive boundary)."""
        return self.start_date <= d <= self.end_date

    def __repr__(self) -> str:
        return f"<FacultyLeave {self.start_date} to {self.end_date}>"


# ── Academic ──────────────────────────────────────────────────────────────


class Course(Base):
    __tablename__ = "course"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    department_id = Column(PGUUID(as_uuid=True), ForeignKey("department.id", ondelete="RESTRICT"), nullable=False)
    requires_lab = Column(Boolean, nullable=False, default=False)
    # If not NULL, the assigned faculty must have a FacultyExpertise record
    # with course_tag == required_expertise_tag (HC-06).
    required_expertise_tag = Column(String(100), nullable=True)

    department = relationship("Department", back_populates="courses")
    tags = relationship("CourseTag", back_populates="course", cascade="all, delete-orphan")
    timetable_entries = relationship("TimetableEntry", back_populates="course")

    def __repr__(self) -> str:
        return f"<Course {self.code}>"


class CourseTag(Base):
    __tablename__ = "course_tag"
    __table_args__ = (UniqueConstraint("course_id", "tag", name="uq_course_tag"),)

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(PGUUID(as_uuid=True), ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    tag = Column(String(100), nullable=False)

    course = relationship("Course", back_populates="tags")


class Section(Base):
    __tablename__ = "section"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)
    department_id = Column(PGUUID(as_uuid=True), ForeignKey("department.id", ondelete="RESTRICT"), nullable=False)
    enrollment = Column(Integer, nullable=False)
    year_of_study = Column(SmallInteger, nullable=False)

    department = relationship("Department", back_populates="sections")
    timetable_entries = relationship("TimetableEntry", back_populates="section")

    def __repr__(self) -> str:
        return f"<Section {self.name} Yr{self.year_of_study}>"


# ── Infrastructure ────────────────────────────────────────────────────────


class Room(Base):
    __tablename__ = "room"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    capacity = Column(Integer, nullable=False)
    is_lab = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    timetable_entries = relationship("TimetableEntry", back_populates="room")
    override_occurrences = relationship("ClassOccurrence", back_populates="override_room", foreign_keys="ClassOccurrence.override_room_id")

    def __repr__(self) -> str:
        return f"<Room {self.name} cap={self.capacity} lab={self.is_lab}>"


# ── Timetable (recurring template) ───────────────────────────────────────


class Period(Base):
    """
    A recurring weekly time slot.
    weekday: 0=Monday … 4=Friday (Sunday=6 not used in current schedule).
    duration_hours property: used for HC-07 workload calculations.
    """
    __tablename__ = "period"
    __table_args__ = (
        UniqueConstraint("weekday", "start_time", name="uq_period_weekday_start"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_period_weekday"),
        CheckConstraint("end_time > start_time", name="ck_period_times"),
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    weekday = Column(SmallInteger, nullable=False)  # 0=Mon … 6=Sun
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    label = Column(String(20), nullable=False)  # e.g. "P1", "P2"

    timetable_entries = relationship("TimetableEntry", back_populates="period")

    @property
    def duration_hours(self) -> float:
        """
        Actual duration of this period in hours.
        Used for faculty workload calculation (HC-07).
        Approved in M0 review: use actual period duration, not an assumed 1h.
        """
        start_mins = self.start_time.hour * 60 + self.start_time.minute
        end_mins = self.end_time.hour * 60 + self.end_time.minute
        return (end_mins - start_mins) / 60.0

    @property
    def weekday_name(self) -> str:
        return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][self.weekday]

    def __repr__(self) -> str:
        return f"<Period {self.weekday_name} {self.label} {self.start_time}-{self.end_time}>"


class TimetableEntry(Base):
    """
    Recurring weekly class assignment (template).

    Unique constraint: (section_id, period_id) — one class per section per slot.
    Faculty and room uniqueness is NOT enforced at DB level; the rule engine
    (M2) detects HC-01 and HC-02 violations.  This allows the seed to plant
    deliberate conflicts for demonstration purposes.
    """
    __tablename__ = "timetable_entry"
    __table_args__ = (
        UniqueConstraint("section_id", "period_id", name="uq_timetable_section_period"),
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id = Column(PGUUID(as_uuid=True), ForeignKey("section.id", ondelete="RESTRICT"), nullable=False)
    course_id = Column(PGUUID(as_uuid=True), ForeignKey("course.id", ondelete="RESTRICT"), nullable=False)
    faculty_id = Column(PGUUID(as_uuid=True), ForeignKey("faculty.id", ondelete="RESTRICT"), nullable=False)
    room_id = Column(PGUUID(as_uuid=True), ForeignKey("room.id", ondelete="RESTRICT"), nullable=False)
    period_id = Column(PGUUID(as_uuid=True), ForeignKey("period.id", ondelete="RESTRICT"), nullable=False)

    section = relationship("Section", back_populates="timetable_entries")
    course = relationship("Course", back_populates="timetable_entries")
    faculty = relationship("Faculty", back_populates="timetable_entries", foreign_keys=[faculty_id])
    room = relationship("Room", back_populates="timetable_entries")
    period = relationship("Period", back_populates="timetable_entries")
    occurrences = relationship("ClassOccurrence", back_populates="timetable_entry", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TimetableEntry section={self.section_id} period={self.period_id}>"


# ── Dated occurrences ─────────────────────────────────────────────────────


class ClassOccurrence(Base):
    """
    A specific dated instance of a TimetableEntry.

    Temporal model:
      - timetable_entry = recurring template (every Monday 09:00).
      - class_occurrence = a specific date (e.g. 2026-11-02 Monday 09:00).
      - override_faculty_id: replacement for THIS occurrence only.
        Setting this DOES NOT modify timetable_entry.faculty_id.
      - HC-10 is enforced by the simulation layer: a simulation result must
        never write to this table's override fields for proposed plans.

    On-demand generation:
      Occurrences are pre-generated for a 6-week window by the seed script.
      The timetable service generates additional occurrences on demand when
      a query requests a date outside the pre-generated window.
      Duplicate prevention: UNIQUE constraint on (timetable_entry_id, occurrence_date).
    """
    __tablename__ = "class_occurrence"
    __table_args__ = (
        UniqueConstraint(
            "timetable_entry_id", "occurrence_date",
            name="uq_occurrence_entry_date",
        ),
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timetable_entry_id = Column(
        PGUUID(as_uuid=True), ForeignKey("timetable_entry.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    occurrence_date = Column(Date, nullable=False, index=True)
    # NULL = inherit from timetable_entry; set only for actual approved replacements
    override_faculty_id = Column(
        PGUUID(as_uuid=True), ForeignKey("faculty.id", ondelete="SET NULL"),
        nullable=True,
    )
    override_room_id = Column(
        PGUUID(as_uuid=True), ForeignKey("room.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(
        SAEnum(OccurrenceStatusEnum, name="occurrencestatusenum"),
        nullable=False,
        default=OccurrenceStatusEnum.scheduled,
    )

    timetable_entry = relationship("TimetableEntry", back_populates="occurrences")
    override_faculty = relationship("Faculty", back_populates="override_occurrences", foreign_keys=[override_faculty_id])
    override_room = relationship("Room", back_populates="override_occurrences", foreign_keys=[override_room_id])

    @property
    def effective_faculty_id(self):
        return self.override_faculty_id or self.timetable_entry.faculty_id

    @property
    def effective_room_id(self):
        return self.override_room_id or self.timetable_entry.room_id

    def __repr__(self) -> str:
        return f"<ClassOccurrence entry={self.timetable_entry_id} date={self.occurrence_date}>"


# ── Decision & Audit ──────────────────────────────────────────────────────


class Decision(Base):
    """
    Immutable audit record of a simulation or human-approved decision.

    IMPORTANT: Approving a decision DOES NOT automatically modify timetable
    or class_occurrence operational data.  The intent is recorded here only.
    Any operational change requires a separate explicit action by an authorized
    user (deferred to a future milestone).
    """
    __tablename__ = "decision"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario = Column(JSONB, nullable=False)
    created_by_id = Column(
        PGUUID(as_uuid=True), ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    decision_status = Column(
        SAEnum(DecisionStatusEnum, name="decisionstatusenum"),
        nullable=False,
        default=DecisionStatusEnum.simulation,
    )
    selected_plan_index = Column(Integer, nullable=True)
    solver_status = Column(String(50), nullable=True)
    llm_status = Column(String(100), nullable=True)
    runtime_ms = Column(Integer, nullable=True)

    created_by_user = relationship("User", back_populates="decisions")
    evidence = relationship("DecisionEvidence", back_populates="decision", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Decision {self.id} {self.decision_status}>"


class DecisionEvidence(Base):
    __tablename__ = "decision_evidence"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(
        PGUUID(as_uuid=True), ForeignKey("decision.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    ref_type = Column(String(50), nullable=False)  # e.g. "faculty", "course", "rule"
    ref_id = Column(PGUUID(as_uuid=True), nullable=True)  # FK to referenced entity (if applicable)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    decision = relationship("Decision", back_populates="evidence")

    def __repr__(self) -> str:
        return f"<DecisionEvidence {self.ref_type} {self.ref_id}>"
