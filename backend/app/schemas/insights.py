from datetime import datetime
from typing import Any

from pydantic import field_validator

from app.schemas.common import ORMModel
from app.schemas.resources import normalize_output_datetime


class InsightRead(ORMModel):
    id: int
    lecture_id: int
    kind: str
    text: str
    evidence_json: dict[str, Any]
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def convert_created_at_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)
