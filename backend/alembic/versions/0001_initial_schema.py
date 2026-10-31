"""Initial schema — M1

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-31

Creates all tables for M1:
    department, user, faculty, faculty_expertise, faculty_leave,
    course, course_tag, section, room, period,
    timetable_entry, class_occurrence, decision, decision_evidence

Enums created first to satisfy PostgreSQL dependencies.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────────────────
    roleenum = postgresql.ENUM(
        "principal", "hod", "exam_cell", name="roleenum", create_type=False
    )
    roleenum.create(op.get_bind(), checkfirst=True)

    expertiselevelenum = postgresql.ENUM(
        "primary", "secondary", name="expertiselevelenum", create_type=False
    )
    expertiselevelenum.create(op.get_bind(), checkfirst=True)

    occurrencestatusenum = postgresql.ENUM(
        "scheduled", "cancelled", "covered",
        name="occurrencestatusenum", create_type=False
    )
    occurrencestatusenum.create(op.get_bind(), checkfirst=True)

    decisionstatusenum = postgresql.ENUM(
        "simulation", "approved", "rejected",
        name="decisionstatusenum", create_type=False
    )
    decisionstatusenum.create(op.get_bind(), checkfirst=True)

    # ── department ────────────────────────────────────────────────────────
    op.create_table(
        "department",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── user ──────────────────────────────────────────────────────────────
    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("role", roleenum, nullable=False),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("department.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── faculty ───────────────────────────────────────────────────────────
    op.create_table(
        "faculty",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("employee_code", sa.String(50), nullable=False, unique=True),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("department.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("weekly_max_hours", sa.Float, nullable=False, default=20.0),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── faculty_expertise ─────────────────────────────────────────────────
    op.create_table(
        "faculty_expertise",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "faculty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("faculty.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("course_tag", sa.String(100), nullable=False),
        sa.Column("level", expertiselevelenum, nullable=False),
        sa.UniqueConstraint("faculty_id", "course_tag", name="uq_faculty_expertise"),
    )

    # ── faculty_leave ─────────────────────────────────────────────────────
    op.create_table(
        "faculty_leave",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "faculty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("faculty.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("end_date >= start_date", name="ck_leave_dates"),
    )

    # ── course ────────────────────────────────────────────────────────────
    op.create_table(
        "course",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("department.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requires_lab", sa.Boolean, nullable=False, default=False),
        sa.Column("required_expertise_tag", sa.String(100), nullable=True),
    )

    # ── course_tag ────────────────────────────────────────────────────────
    op.create_table(
        "course_tag",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("course.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(100), nullable=False),
        sa.UniqueConstraint("course_id", "tag", name="uq_course_tag"),
    )

    # ── section ───────────────────────────────────────────────────────────
    op.create_table(
        "section",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("department.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("enrollment", sa.Integer, nullable=False),
        sa.Column("year_of_study", sa.SmallInteger, nullable=False),
    )

    # ── room ──────────────────────────────────────────────────────────────
    op.create_table(
        "room",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("is_lab", sa.Boolean, nullable=False, default=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
    )

    # ── period ────────────────────────────────────────────────────────────
    op.create_table(
        "period",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("weekday", sa.SmallInteger, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("label", sa.String(20), nullable=False),
        sa.UniqueConstraint("weekday", "start_time", name="uq_period_weekday_start"),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_period_weekday"),
        sa.CheckConstraint("end_time > start_time", name="ck_period_times"),
    )

    # ── timetable_entry ───────────────────────────────────────────────────
    op.create_table(
        "timetable_entry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("section.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("course.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "faculty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("faculty.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "room_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("room.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("period.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # One class per section per slot — enforced.
        # Faculty/room uniqueness intentionally NOT enforced at DB level
        # so the seed can plant HC-01 and HC-02 violations for M2.
        sa.UniqueConstraint("section_id", "period_id", name="uq_timetable_section_period"),
    )

    # ── class_occurrence ──────────────────────────────────────────────────
    op.create_table(
        "class_occurrence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "timetable_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("timetable_entry.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("occurrence_date", sa.Date, nullable=False, index=True),
        sa.Column(
            "override_faculty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("faculty.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "override_room_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("room.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            occurrencestatusenum,
            nullable=False,
            server_default="scheduled",
        ),
        sa.UniqueConstraint(
            "timetable_entry_id", "occurrence_date", name="uq_occurrence_entry_date"
        ),
    )

    # ── decision ──────────────────────────────────────────────────────────
    op.create_table(
        "decision",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scenario", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "decision_status",
            decisionstatusenum,
            nullable=False,
            server_default="simulation",
        ),
        sa.Column("selected_plan_index", sa.Integer, nullable=True),
        sa.Column("solver_status", sa.String(50), nullable=True),
        sa.Column("llm_status", sa.String(100), nullable=True),
        sa.Column("runtime_ms", sa.Integer, nullable=True),
    )

    # ── decision_evidence ─────────────────────────────────────────────────
    op.create_table(
        "decision_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("decision.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("ref_type", sa.String(50), nullable=False),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("decision_evidence")
    op.drop_table("decision")
    op.drop_table("class_occurrence")
    op.drop_table("timetable_entry")
    op.drop_table("period")
    op.drop_table("room")
    op.drop_table("section")
    op.drop_table("course_tag")
    op.drop_table("course")
    op.drop_table("faculty_leave")
    op.drop_table("faculty_expertise")
    op.drop_table("faculty")
    op.drop_table("user")
    op.drop_table("department")

    # Drop enums
    for enum_name in ["decisionstatusenum", "occurrencestatusenum", "expertiselevelenum", "roleenum"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

