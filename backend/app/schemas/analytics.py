from datetime import date, datetime
from typing import Literal

from pydantic import field_validator

from app.schemas.common import ORMModel
from app.schemas.resources import normalize_output_datetime

UtilizationClass = Literal["no_data", "underutilized", "well_utilized", "overutilized"]


class OccupancyMinuteRead(ORMModel):
    timestamp: datetime
    average_occupied: float

    @field_validator("timestamp", mode="before")
    @classmethod
    def convert_timestamp_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class UnusedPeriodRead(ORMModel):
    lecture_id: int
    start: datetime
    end: datetime

    @field_validator("start", "end", mode="before")
    @classmethod
    def convert_period_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class LectureAnalyticsRead(ORMModel):
    lecture_id: int
    classroom_id: int
    capacity: int
    enrolled_students: int
    average_occupancy: float
    peak_occupancy: int
    peak_time: datetime | None
    utilization_percent: float
    exit_count: int
    outside_minutes: float
    occupancy_by_minute: list[OccupancyMinuteRead]
    unused_periods: list[UnusedPeriodRead]

    @field_validator("peak_time", mode="before")
    @classmethod
    def convert_peak_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_output_datetime(value)


class ClassroomUtilizationRead(ORMModel):
    classroom_id: int
    classroom_name: str
    capacity: int
    from_date: date | None
    to_date: date | None
    lecture_count: int
    average_occupancy: float
    peak_occupancy: int
    peak_time: datetime | None
    utilization_percent: float
    exit_count: int
    unused_minutes: float
    unused_periods: list[UnusedPeriodRead]
    classification: UtilizationClass
    simulated: bool
    suggestion: str

    @field_validator("peak_time", mode="before")
    @classmethod
    def convert_peak_to_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_output_datetime(value)


class OutsideDurationBucket(ORMModel):
    period_start: date
    lecture_count: int
    outside_minutes: float


class OutsideDurationRead(ORMModel):
    period: Literal["day", "week", "month"]
    total_outside_minutes: float
    buckets: list[OutsideDurationBucket]
