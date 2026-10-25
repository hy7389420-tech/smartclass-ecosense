from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.activity import EngagementRead
from app.schemas.attendance import AttendanceStatus, AttendanceStudentRead
from app.schemas.common import ORMModel
from app.schemas.resources import normalize_output_datetime

ReportFormat = Literal["json", "csv"]
ReportPeriod = Literal["daily", "weekly"]


class ReportLectureRead(ORMModel):
    lecture_id: int
    subject: str
    status: str
    classroom_id: int
    classroom_name: str
    capacity: int
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class ReportAttendanceSummary(ORMModel):
    total_students: int
    present: int
    inside: int
    outside: int
    absent: int
    occupancy_percent: float


class SessionReportRead(ORMModel):
    lecture: ReportLectureRead
    attendance_summary: ReportAttendanceSummary | None
    student_records: list[AttendanceStudentRead]
    engagement: EngagementRead | None
    estimates_note: str | None
    limitations_note: str


class LectureSummaryRead(ORMModel):
    lecture_id: int
    subject: str
    start_time: datetime
    total_students: int | None
    present: int | None
    inside: int | None
    outside: int | None
    absent: int | None
    inside_minutes: float | None
    outside_minutes: float | None
    status: AttendanceStatus | None = None
    student_id: int | None = None

    @field_validator("start_time", mode="before")
    @classmethod
    def normalize_start_time(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class SummaryReportRead(ORMModel):
    period: ReportPeriod
    start_date: date
    end_date: date
    lecture_count: int
    rows: list[LectureSummaryRead]
    limitations_note: str


class RetentionRequest(ORMModel):
    dry_run: bool = True


class RetentionRunRead(ORMModel):
    dry_run: bool
    retention_days: int = Field(ge=1)
    cutoff_at: datetime
    candidates: dict[str, int]
    deleted: dict[str, int]
    correction_links_to_detach: int = Field(ge=0)

    @field_validator("cutoff_at", mode="before")
    @classmethod
    def normalize_cutoff(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)
