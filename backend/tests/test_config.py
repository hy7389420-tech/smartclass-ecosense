import pytest
from pydantic import ValidationError

from app.config import Settings


def test_activity_configuration_defaults_and_validation():
    settings = Settings()
    assert settings.activity_movement_weight == 0.3
    assert settings.activity_audio_weight == 0.1
    assert settings.activity_min_signals == 2

    with pytest.raises(ValidationError, match="At least one activity signal weight"):
        Settings(
            activity_movement_weight=0,
            activity_inactivity_weight=0,
            activity_head_weight=0,
            activity_voice_weight=0,
            activity_audio_weight=0,
        )
    with pytest.raises(ValidationError, match="must exceed ACTIVITY_LOW_CUTOFF"):
        Settings(activity_low_cutoff=0.7, activity_high_cutoff=0.6)
    with pytest.raises(
        ValidationError, match="must exceed ACTIVITY_DECLINE_LAST_WINDOWS"
    ):
        Settings(activity_decline_last_windows=4, activity_decline_min_windows=4)


def test_blank_development_jwt_secret_is_generated():
    settings = Settings(jwt_secret_key="", app_env="development")
    assert len(settings.jwt_secret_key) >= 32


def test_production_rejects_weak_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(jwt_secret_key="short", app_env="production")
