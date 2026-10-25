from datetime import datetime
from typing import Literal

from pydantic import field_validator

from app.schemas.common import ORMModel
from app.schemas.resources import normalize_output_datetime

AttendanceStatus = Literal["ABSENT", "INSIDE", "OUTSIDE", "PARTIAL"]


class AttendanceStudentRead(ORMModel):
    student_id: int
    student_code: str
    name: str
    status: AttendanceStatus
    first_entry: datetime | None
    last_exit: datetime | None
    inside_minutes: float
    outside_minutes: float
    exit_count: int
    return_count: int
    flagged: bool

    @field_validator("first_entry", "last_exit", mode="before")
    @classmethod
    def convert_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_output_datetime(value)


class AttendanceResponse(ORMModel):
    lecture_id: int
    lecture_status: str
    finalized: bool
    total_students: int
    present: int
    inside: int
    outside: int
    absent: int
    occupancy_percent: float
    records: list[AttendanceStudentRead]


class PresenceHistoryItem(ORMModel):
    lecture_id: int
    subject: str
    lecture_start: datetime
    lecture_end: datetime
    status: AttendanceStatus
    first_entry: datetime | None
    last_exit: datetime | None
    inside_minutes: float
    outside_minutes: float
    exit_count: int
    return_count: int

    @field_validator(
        "lecture_start", "lecture_end", "first_entry", "last_exit", mode="before"
    )
    @classmethod
    def convert_datetimes_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_output_datetime(value)
