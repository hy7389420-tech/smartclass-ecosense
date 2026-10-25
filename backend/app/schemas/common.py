from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

ItemT = TypeVar("ItemT")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampedRead(ORMModel):
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_utc_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    total: int
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
