import pytest
from pydantic import ValidationError

from app.config import Settings


def test_activity_configuration_defaults_and_validation():
    settings = Settings()
    assert settings.activity_movement_weight == 0.3
    assert settings.activity_audio_weight == 0.1
    assert settings.activity_min_signals == 2
    assert settings.activity_smoothing_windows == 2
    assert settings.activity_min_windows_for_stats == 3
    assert settings.activity_peak_z == 1.0
    assert settings.activity_decline_min_baseline_windows == 3

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
    with pytest.raises(ValidationError):
        Settings(activity_smoothing_windows=0)
    with pytest.raises(ValidationError):
        Settings(activity_decline_min_baseline_windows=0)
    with pytest.raises(ValidationError):
        Settings(activity_peak_z=float("nan"))


def test_blank_development_jwt_secret_is_generated():
    settings = Settings(jwt_secret_key="", app_env="development")
    assert len(settings.jwt_secret_key) >= 32


def test_production_rejects_weak_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(jwt_secret_key="short", app_env="production")


def test_production_rejects_default_like_jwt_secret():
    with pytest.raises(ValidationError, match="non-default secret"):
        Settings(
            jwt_secret_key="change-me-this-is-a-long-default-secret-value",
            app_env="production",
        )


@pytest.mark.parametrize(
    "origins",
    [
        "*",
        "https://example.test/path",
        "javascript://example.test",
        "https://user:password@example.test",
    ],
)
def test_cors_rejects_wildcard_and_non_origin_values(origins):
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        Settings(cors_allowed_origins=origins)


def test_security_limit_defaults_and_bounds():
    settings = Settings()
    assert settings.max_request_body_bytes == 1_048_576
    assert settings.request_rate_limit_requests == 120
    assert settings.auth_rate_limit_requests == 30
    assert settings.event_rate_limit_requests == 30
    with pytest.raises(ValidationError):
        Settings(max_request_body_bytes=128)


def test_ai_assistant_is_disabled_by_default():
    assert Settings().ai_assistant_enabled is False


def test_simulator_retry_defaults_and_bounds():
    settings = Settings()
    assert settings.simulator_request_timeout_seconds == 10
    assert settings.simulator_retry_attempts == 3
    assert settings.simulator_retry_backoff_seconds == 1
    with pytest.raises(ValidationError):
        Settings(simulator_retry_attempts=11)
    with pytest.raises(ValidationError):
        Settings(simulator_retry_backoff_seconds=31)
