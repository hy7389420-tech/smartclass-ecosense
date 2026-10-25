from datetime import datetime
from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator

from app.schemas.attendance import AttendanceResponse
from app.schemas.common import ORMModel, PaginatedResponse
from app.schemas.events import PresenceEventRead
from app.schemas.resources import normalize_output_datetime


class ReviewQueueRead(PaginatedResponse[PresenceEventRead]):
    pass


class EventCorrectionRead(ORMModel):
    event: PresenceEventRead
    attendance: AttendanceResponse


class AuditLogRead(ORMModel):
    id: int
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: str
    before_json: dict[str, object] | None
    after_json: dict[str, object] | None
    reason: str | None
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class AlertRead(ORMModel):
    id: int
    kind: str
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    classroom_id: int | None
    lecture_id: int | None
    camera_id: int | None
    created_at: datetime
    resolved_at: datetime | None

    @field_validator("created_at", "resolved_at", mode="before")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return normalize_output_datetime(value) if value is not None else None


class AlertResolveWrite(ORMModel):
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]


class HeartbeatRead(ORMModel):
    camera_id: int
    status: Literal["online"]
    last_seen_at: datetime

    @field_validator("last_seen_at", mode="before")
    @classmethod
    def normalize_last_seen_at(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)
