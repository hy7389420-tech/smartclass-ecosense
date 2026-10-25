from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, field_validator

from app.schemas.common import ORMModel, TimestampedRead
from app.schemas.resources import normalize_input_datetime, normalize_output_datetime

RawEventType = Literal["ENTRY", "EXIT"]
StoredEventType = Literal[
    "ENTRY", "EXIT", "RETURN", "LECTURE_START", "LECTURE_END", "MANUAL_CORRECTION"
]
EventSource = Literal["camera", "simulator", "manual"]
StudentCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
ClientEventId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]


class EventIngestRequest(ORMModel):
    model_config = ConfigDict(extra="ignore")

    student_id: StudentCode
    classroom_id: int | str
    lecture_id: int | str
    event_type: RawEventType
    timestamp: datetime
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    source: EventSource
    flagged_for_review: bool = False
    presence_confirmed: bool = False
    client_event_id: ClientEventId | None = None

    @field_validator("timestamp")
    @classmethod
    def convert_timestamp_to_utc(cls, value: datetime) -> datetime:
        return normalize_input_datetime(value)


class PresenceEventRead(TimestampedRead):
    id: int
    client_event_id: str | None
    lecture_id: int
    classroom_id: int
    student_id: int | None
    correction_of_event_id: int | None = None
    correction_event_type: Literal["ENTRY", "EXIT", "RETURN"] | None = None
    student_code_raw: str | None
    event_type: StoredEventType
    timestamp_utc: datetime
    confidence: float
    source: str
    flagged_for_review: bool
    review_status: str
    presence_confirmed: bool

    @field_validator("timestamp_utc", mode="before")
    @classmethod
    def convert_timestamp_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class EventIngestResponse(ORMModel):
    event: PresenceEventRead
    duplicate: bool
    flagged_for_review: bool
    reason: str | None


class EventBatchResponse(ORMModel):
    items: list[EventIngestResponse]
    accepted_count: int
    flagged_count: int
    duplicate_count: int


class EventCorrectionWrite(ORMModel):
    student_id: int | None = Field(default=None, gt=0)
    event_type: Literal["ENTRY", "EXIT"]
    timestamp: datetime
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]

    @field_validator("timestamp")
    @classmethod
    def convert_timestamp_to_utc(cls, value: datetime) -> datetime:
        return normalize_input_datetime(value)


class ReviewResolutionWrite(ORMModel):
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]
