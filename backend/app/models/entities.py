from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ClassGroup(Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint(
            "department_id",
            "name",
            "section",
            "year",
            name="uq_classes_department_name_section_year",
        ),
        CheckConstraint("year >= 1", name="year_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    section: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Classroom(Base):
    __tablename__ = "classrooms"
    __table_args__ = (CheckConstraint("capacity > 0", name="capacity_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("class_id", "roll_no", name="uq_students_class_roll"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    roll_no: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'HOD', 'FACULTY', 'STUDENT')",
            name="role_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Faculty(Base):
    __tablename__ = "faculty"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"), nullable=False, index=True
    )
    employee_code: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )


class FacultyClassAssignment(Base):
    __tablename__ = "faculty_class_assignments"
    __table_args__ = (
        UniqueConstraint("faculty_id", "class_id", name="uq_faculty_class_assignment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("faculty.id"), nullable=False)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Lecture(Base):
    __tablename__ = "lectures"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="end_after_start"),
        CheckConstraint(
            "status IN ('scheduled', 'live', 'completed', 'cancelled')",
            name="lecture_status_valid",
        ),
        Index(
            "ix_lectures_classroom_start_end", "classroom_id", "start_time", "end_time"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id"), nullable=False, index=True
    )
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    faculty_id: Mapped[int | None] = mapped_column(
        ForeignKey("faculty.id"), nullable=True
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="offline", nullable=False)


class PresenceEvent(Base):
    __tablename__ = "presence_events"
    __table_args__ = (
        UniqueConstraint(
            "lecture_id", "client_event_id", name="uq_presence_events_lecture_client_id"
        ),
        CheckConstraint(
            "event_type IN ('ENTRY', 'EXIT', 'RETURN', 'LECTURE_START', "
            "'LECTURE_END', 'MANUAL_CORRECTION')",
            name="event_type_valid",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        Index("ix_presence_events_lecture_timestamp", "lecture_id", "timestamp_utc"),
        Index("ix_presence_events_lecture_student", "lecture_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id"), nullable=False)
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id"), nullable=False
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id"), nullable=True, index=True
    )
    student_code_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    flagged_for_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    review_status: Mapped[str] = mapped_column(
        String(32), default="not_required", nullable=False
    )
    presence_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "lecture_id", "student_id", name="uq_attendance_lecture_student"
        ),
        CheckConstraint(
            "status IN ('ABSENT', 'INSIDE', 'OUTSIDE', 'PARTIAL')",
            name="attendance_status_valid",
        ),
        CheckConstraint("inside_minutes >= 0", name="inside_minutes_nonnegative"),
        CheckConstraint("outside_minutes >= 0", name="outside_minutes_nonnegative"),
        CheckConstraint("exit_count >= 0", name="exit_count_nonnegative"),
        CheckConstraint("return_count >= 0", name="return_count_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    first_entry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_exit: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    inside_minutes: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    outside_minutes: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    exit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    return_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ActivityWindow(Base):
    __tablename__ = "activity_windows"
    __table_args__ = (
        CheckConstraint("window_end > window_start", name="window_end_after_start"),
        UniqueConstraint(
            "lecture_id", "window_start", name="uq_activity_lecture_window_start"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id"), nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    movement_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    inactivity_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    front_facing_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_level_db_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    voice_activity_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        CheckConstraint("severity IN ('low', 'medium', 'high')", name="severity_valid"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'ignored')",
            name="suggestion_status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class SuggestionDecision(Base):
    __tablename__ = "suggestion_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('accepted', 'rejected', 'ignored')",
            name="decision_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    suggestion_id: Mapped[int] = mapped_column(
        ForeignKey("suggestions.id"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    decided_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="severity_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    classroom_id: Mapped[int | None] = mapped_column(
        ForeignKey("classrooms.id"), nullable=True
    )
    lecture_id: Mapped[int | None] = mapped_column(
        ForeignKey("lectures.id"), nullable=True
    )
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
