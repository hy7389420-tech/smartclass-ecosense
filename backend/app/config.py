import secrets
from functools import lru_cache
from math import isfinite

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./ecosense.db"
    local_timezone: str = "Asia/Kolkata"
    require_camera_key: bool = True
    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    jwt_access_token_minutes: int = Field(default=15, ge=1, le=60)
    auth_login_max_attempts: int = Field(default=5, ge=1, le=100)
    auth_login_window_seconds: int = Field(default=60, ge=1, le=3600)
    event_time_grace_seconds: int = Field(default=300, ge=0)
    min_event_confidence: float = Field(default=0.5, ge=0, le=1)
    max_event_batch_size: int = Field(default=100, ge=1, le=1000)
    camera_offline_seconds: int = Field(default=120, ge=1)
    low_confidence_alert_window_minutes: int = Field(default=5, ge=1, le=60)
    low_confidence_alert_min_events: int = Field(default=3, ge=1)
    unusual_exit_alert_window_minutes: int = Field(default=5, ge=1, le=60)
    unusual_exit_alert_min_events: int = Field(default=3, ge=1)
    underutilized_cutoff_percent: float = Field(default=40, ge=0, le=100)
    overutilized_cutoff_percent: float = Field(default=90, ge=0, le=100)
    insight_window_minutes: int = Field(default=5, ge=1, le=60)
    insight_min_exits: int = Field(default=3, ge=1)
    insight_min_buckets: int = Field(default=3, ge=1)
    insight_min_history: int = Field(default=3, ge=1)
    insight_history_lectures: int = Field(default=5, ge=1)
    activity_max_batch_size: int = Field(default=100, ge=1, le=1000)
    activity_min_window_seconds: int = Field(default=1, ge=1)
    activity_max_window_seconds: int = Field(default=300, ge=1)
    activity_movement_min: float = 0.0
    activity_movement_max: float = 1.0
    activity_front_min: float = 0.0
    activity_front_max: float = 1.0
    activity_voice_min: float = 0.0
    activity_voice_max: float = 1.0
    activity_audio_min_dbfs: float = Field(default=-120.0, le=0)
    activity_audio_max_dbfs: float = Field(default=0.0, le=0)
    activity_movement_weight: float = Field(default=0.30, ge=0, le=1)
    activity_inactivity_weight: float = Field(default=0.20, ge=0, le=1)
    activity_head_weight: float = Field(default=0.20, ge=0, le=1)
    activity_voice_weight: float = Field(default=0.20, ge=0, le=1)
    activity_audio_weight: float = Field(default=0.10, ge=0, le=1)
    activity_min_signals: int = Field(default=2, ge=1, le=5)
    activity_low_cutoff: float = Field(default=0.35, ge=0, le=1)
    activity_high_cutoff: float = Field(default=0.65, ge=0, le=1)
    activity_low_run_windows: int = Field(default=3, ge=1)
    activity_peak_count: int = Field(default=3, ge=1)
    activity_decline_last_windows: int = Field(default=3, ge=1)
    activity_decline_min_windows: int = Field(default=6, ge=2)
    activity_decline_threshold: float = Field(default=0.20, ge=0, le=1)
    activity_voice_low_threshold: float = Field(default=0.20, ge=0, le=1)
    activity_voice_min_windows: int = Field(default=3, ge=1)
    activity_movement_spike_threshold: float = Field(default=0.60, ge=0, le=1)
    activity_noise_threshold_dbfs: float = Field(default=-35, ge=-120, le=0)
    activity_max_suggestions: int = Field(default=4, ge=1, le=6)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def utilization_cutoffs_are_ordered(self) -> "Settings":
        if not self.jwt_secret_key.strip() and self.app_env.lower() != "production":
            self.jwt_secret_key = secrets.token_urlsafe(48)
        if self.app_env.lower() == "production" and len(self.jwt_secret_key) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must contain at least 32 characters in production."
            )
        activity_numbers = (
            self.activity_movement_min,
            self.activity_movement_max,
            self.activity_front_min,
            self.activity_front_max,
            self.activity_voice_min,
            self.activity_voice_max,
            self.activity_audio_min_dbfs,
            self.activity_audio_max_dbfs,
            self.activity_movement_weight,
            self.activity_inactivity_weight,
            self.activity_head_weight,
            self.activity_voice_weight,
            self.activity_audio_weight,
            self.activity_low_cutoff,
            self.activity_high_cutoff,
            self.activity_decline_threshold,
            self.activity_voice_low_threshold,
            self.activity_movement_spike_threshold,
            self.activity_noise_threshold_dbfs,
        )
        if not all(isfinite(value) for value in activity_numbers):
            raise ValueError("Activity settings must contain only finite numbers.")
        if self.overutilized_cutoff_percent <= self.underutilized_cutoff_percent:
            raise ValueError(
                "OVERUTILIZED_CUTOFF_PERCENT must exceed UNDERUTILIZED_CUTOFF_PERCENT."
            )
        if self.activity_max_window_seconds < self.activity_min_window_seconds:
            raise ValueError(
                "ACTIVITY_MAX_WINDOW_SECONDS must be at least "
                "ACTIVITY_MIN_WINDOW_SECONDS."
            )
        if self.activity_audio_max_dbfs <= self.activity_audio_min_dbfs:
            raise ValueError(
                "ACTIVITY_AUDIO_MAX_DBFS must exceed ACTIVITY_AUDIO_MIN_DBFS."
            )
        for name, minimum, maximum in (
            (
                "MOVEMENT",
                self.activity_movement_min,
                self.activity_movement_max,
            ),
            ("FRONT", self.activity_front_min, self.activity_front_max),
            ("VOICE", self.activity_voice_min, self.activity_voice_max),
        ):
            if minimum < 0 or maximum > 1 or maximum <= minimum:
                raise ValueError(
                    f"ACTIVITY_{name}_MIN/MAX must be ordered within 0 and 1."
                )
        if self.activity_high_cutoff <= self.activity_low_cutoff:
            raise ValueError("ACTIVITY_HIGH_CUTOFF must exceed ACTIVITY_LOW_CUTOFF.")
        if self.activity_decline_min_windows <= self.activity_decline_last_windows:
            raise ValueError(
                "ACTIVITY_DECLINE_MIN_WINDOWS must exceed "
                "ACTIVITY_DECLINE_LAST_WINDOWS."
            )
        if (
            sum(
                (
                    self.activity_movement_weight,
                    self.activity_inactivity_weight,
                    self.activity_head_weight,
                    self.activity_voice_weight,
                    self.activity_audio_weight,
                )
            )
            <= 0
        ):
            raise ValueError("At least one activity signal weight must be positive.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
