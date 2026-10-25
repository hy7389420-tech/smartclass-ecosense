from datetime import UTC, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.config import get_settings
from app.schemas.common import ORMModel, TimestampedRead

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]


class DepartmentWrite(ORMModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]


class DepartmentRead(TimestampedRead):
    id: int
    name: str


class ClassWrite(ORMModel):
    department_id: int = Field(gt=0)
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    section: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] = (
        ""
    )
    year: int = Field(ge=1)


class ClassRead(TimestampedRead):
    id: int
    department_id: int
    name: str
    section: str
    year: int


class ClassroomWrite(ORMModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    capacity: int = Field(gt=0)


class ClassroomRead(TimestampedRead):
    id: int
    name: str
    capacity: int


class StudentWrite(ORMModel):
    student_code: ShortText
    roll_no: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
    ]
    name: Name
    class_id: int = Field(gt=0)
    is_active: bool = True


class StudentRead(TimestampedRead):
    id: int
    student_code: str
    roll_no: str
    name: str
    class_id: int
    is_active: bool


def normalize_input_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        timezone = ZoneInfo(get_settings().local_timezone)
        value = value.replace(tzinfo=timezone)
    return value.astimezone(UTC)


def normalize_output_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class LectureWrite(ORMModel):
    classroom_id: int = Field(gt=0)
    class_id: int = Field(gt=0)
    subject: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
    ]
    faculty_id: int | None = Field(default=None, gt=0)
    start_time: datetime
    end_time: datetime
    status: Literal["scheduled", "live", "completed", "cancelled"] = "scheduled"

    @field_validator("start_time", "end_time")
    @classmethod
    def convert_to_utc(cls, value: datetime) -> datetime:
        return normalize_input_datetime(value)

    @model_validator(mode="after")
    def lecture_end_must_follow_start(self) -> "LectureWrite":
        if self.end_time <= self.start_time:
            raise ValueError("Lecture end time must be after start time.")
        return self


class LectureRead(TimestampedRead):
    id: int
    classroom_id: int
    class_id: int
    subject: str
    faculty_id: int | None
    start_time: datetime
    end_time: datetime
    status: str

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def convert_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)
