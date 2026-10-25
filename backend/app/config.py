from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./ecosense.db"
    local_timezone: str = "Asia/Kolkata"
    require_camera_key: bool = True
    event_time_grace_seconds: int = Field(default=300, ge=0)
    min_event_confidence: float = Field(default=0.5, ge=0, le=1)
    max_event_batch_size: int = Field(default=100, ge=1, le=1000)
    camera_online_window_seconds: int = Field(default=120, ge=1)
    underutilized_cutoff_percent: float = Field(default=40, ge=0, le=100)
    overutilized_cutoff_percent: float = Field(default=90, ge=0, le=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def utilization_cutoffs_are_ordered(self) -> "Settings":
        if self.overutilized_cutoff_percent <= self.underutilized_cutoff_percent:
            raise ValueError(
                "OVERUTILIZED_CUTOFF_PERCENT must exceed UNDERUTILIZED_CUTOFF_PERCENT."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
