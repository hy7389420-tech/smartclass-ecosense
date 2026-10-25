from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.resources import normalize_output_datetime


class SuggestionRead(ORMModel):
    id: int
    lecture_id: int
    rule_id: str
    title: str
    text: str
    evidence_json: dict[str, Any]
    severity: Literal["low", "medium", "high"]
    status: Literal["pending", "accepted", "rejected", "ignored"]
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def convert_created_at_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class SuggestionDecisionWrite(ORMModel):
    decision: Literal["accepted", "rejected", "ignored"]
    note: str | None = Field(default=None, max_length=1000)


class SuggestionDecisionRead(ORMModel):
    id: int
    suggestion_id: int
    decision: Literal["accepted", "rejected", "ignored"]
    decided_by: int
    decided_at: datetime
    note: str | None

    @field_validator("decided_at", mode="before")
    @classmethod
    def convert_decided_at_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)
