from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.config import get_settings
from app.schemas.common import ORMModel
from app.schemas.resources import normalize_input_datetime, normalize_output_datetime

ActivitySource = Literal["camera+mic", "simulated", "manual"]


class ActivityWindowWrite(ORMModel):
    lecture_id: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    movement_level: float | None = Field(default=None, allow_inf_nan=False)
    inactivity_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    front_facing_ratio: float | None = Field(default=None, allow_inf_nan=False)
    audio_level_db_mean: float | None = Field(default=None, allow_inf_nan=False)
    voice_activity_ratio: float | None = Field(default=None, allow_inf_nan=False)
    source: ActivitySource

    @field_validator("window_start", "window_end")
    @classmethod
    def convert_times_to_utc(cls, value: datetime) -> datetime:
        return normalize_input_datetime(value)

    @model_validator(mode="after")
    def validate_activity_window(self) -> "ActivityWindowWrite":
        settings = get_settings()
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start.")
        duration = (self.window_end - self.window_start).total_seconds()
        if not (
            settings.activity_min_window_seconds
            <= duration
            <= settings.activity_max_window_seconds
        ):
            raise ValueError("Activity window duration is outside configured limits.")
        if self.inactivity_seconds is not None and self.inactivity_seconds > duration:
            raise ValueError("inactivity_seconds must fit inside the activity window.")
        _validate_range(
            "movement_level",
            self.movement_level,
            settings.activity_movement_min,
            settings.activity_movement_max,
        )
        _validate_range(
            "front_facing_ratio",
            self.front_facing_ratio,
            settings.activity_front_min,
            settings.activity_front_max,
        )
        _validate_range(
            "voice_activity_ratio",
            self.voice_activity_ratio,
            settings.activity_voice_min,
            settings.activity_voice_max,
        )
        _validate_range(
            "audio_level_db_mean",
            self.audio_level_db_mean,
            settings.activity_audio_min_dbfs,
            settings.activity_audio_max_dbfs,
        )
        return self


def _validate_range(
    name: str, value: float | None, minimum: float, maximum: float
) -> None:
    if value is not None and not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")


class ActivityWindowRead(ORMModel):
    id: int
    lecture_id: int
    window_start: datetime
    window_end: datetime
    movement_level: float | None
    inactivity_seconds: float | None
    front_facing_ratio: float | None
    audio_level_db_mean: float | None
    voice_activity_ratio: float | None
    source: str

    @field_validator("window_start", "window_end", mode="before")
    @classmethod
    def convert_times_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class ActivityIngestResponse(ORMModel):
    stored_count: int
    duplicate_count: int
    windows: list[ActivityWindowRead]


class EngagementWindowRead(ORMModel):
    window_start: datetime
    window_end: datetime
    estimate: float | None
    label: Literal["high", "medium", "low", "insufficient_data"]
    available_signals: int
    signals: dict[str, float | None]

    @field_validator("window_start", "window_end", mode="before")
    @classmethod
    def convert_times_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class ActivityPeakRead(ORMModel):
    timestamp: datetime
    estimate: float

    @field_validator("timestamp", mode="before")
    @classmethod
    def convert_timestamp_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class LowActivityRunRead(ORMModel):
    start: datetime
    end: datetime
    window_count: int
    average_estimate: float

    @field_validator("start", "end", mode="before")
    @classmethod
    def convert_times_to_utc(cls, value: datetime) -> datetime:
        return normalize_output_datetime(value)


class DeclineRead(ORMModel):
    status: Literal["detected", "not_detected", "insufficient_data"]
    baseline_estimate: float | None
    recent_estimate: float | None
    drop: float | None


class EngagementRead(ORMModel):
    lecture_id: int
    estimate_note: str
    windows: list[EngagementWindowRead]
    average_estimate: float | None
    peaks: list[ActivityPeakRead]
    low_runs: list[LowActivityRunRead]
    decline: DeclineRead
    peak_drop_detected: bool
    peak_estimate: float | None
    recent_estimate: float | None
    voice_activity_average: float | None
    voice_activity_windows: int
    movement_level_max: float | None
    audio_level_average_dbfs: float | None
    valid_window_count: int
    insufficient_window_count: int
