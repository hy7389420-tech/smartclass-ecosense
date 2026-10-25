from datetime import UTC, datetime, timedelta

import pytest

from app.services.fusion import (
    ActivitySignals,
    FusionConfig,
    analyze_activity,
)


def fusion_config(**overrides) -> FusionConfig:
    values = {
        "movement_weight": 0.30,
        "inactivity_weight": 0.20,
        "head_weight": 0.20,
        "voice_weight": 0.20,
        "audio_weight": 0.10,
        "movement_min": 0,
        "movement_max": 1,
        "front_min": 0,
        "front_max": 1,
        "voice_min": 0,
        "voice_max": 1,
        "audio_min_dbfs": -120,
        "audio_max_dbfs": 0,
        "min_signals": 2,
        "low_cutoff": 0.35,
        "high_cutoff": 0.65,
        "low_run_windows": 3,
        "peak_count": 3,
        "decline_last_windows": 3,
        "decline_min_windows": 6,
        "decline_threshold": 0.2,
    }
    values.update(overrides)
    return FusionConfig(**values)


def window(
    index: int,
    score: float,
    *,
    movement: float | None = None,
    voice: float | None = None,
    audio_dbfs: float | None = None,
    inactivity: float | None = None,
    front: float | None = None,
) -> ActivitySignals:
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC) + timedelta(minutes=index)
    return ActivitySignals(
        window_start=start,
        window_end=start + timedelta(minutes=1),
        movement_level=score if movement is None else movement,
        inactivity_seconds=60 * (1 - score) if inactivity is None else inactivity,
        front_facing_ratio=score if front is None else front,
        audio_level_db_mean=(-120 + score * 120 if audio_dbfs is None else audio_dbfs),
        voice_activity_ratio=score if voice is None else voice,
    )


def test_normalizes_all_signals_and_fuses_by_available_weights():
    result = analyze_activity([window(0, 0.5)], fusion_config())

    assert result.windows[0].estimate == 0.5
    assert result.windows[0].label == "medium"
    assert result.windows[0].available_signals == 5
    assert result.windows[0].signals == {
        "movement": 0.5,
        "inactivity_inverted": 0.5,
        "head_front": 0.5,
        "voice_activity": 0.5,
        "audio_level": 0.5,
    }


def test_missing_signals_are_excluded_and_too_few_means_insufficient_data():
    one_signal = ActivitySignals(
        window_start=datetime(2030, 1, 1, 10, tzinfo=UTC),
        window_end=datetime(2030, 1, 1, 10, 1, tzinfo=UTC),
        movement_level=0.8,
    )
    result = analyze_activity([one_signal], fusion_config())

    assert result.windows[0].estimate is None
    assert result.windows[0].label == "insufficient_data"
    assert result.windows[0].available_signals == 1
    assert result.average_estimate is None
    assert result.insufficient_window_count == 1

    two_signals = ActivitySignals(
        window_start=one_signal.window_start,
        window_end=one_signal.window_end,
        movement_level=0.8,
        voice_activity_ratio=0.2,
    )
    fused = analyze_activity([two_signals], fusion_config())
    assert fused.windows[0].estimate == 0.56
    assert fused.windows[0].available_signals == 2


def test_detects_decline_low_run_and_peaks_and_handles_flat_series():
    declining = analyze_activity(
        [window(index, 0.9 if index < 3 else 0.1) for index in range(6)],
        fusion_config(),
    )
    flat = analyze_activity([window(index, 0.5) for index in range(6)], fusion_config())

    assert declining.decline.status == "detected"
    assert declining.decline.baseline_estimate == 0.9
    assert declining.decline.recent_estimate == 0.1
    assert declining.low_runs[0].window_count == 3
    assert declining.peaks[0].estimate == 0.9
    assert flat.decline.status == "not_detected"
    assert flat.low_runs == ()


def test_decline_is_insufficient_until_minimum_window_count():
    result = analyze_activity(
        [window(index, 0.8) for index in range(5)], fusion_config()
    )

    assert result.decline.status == "insufficient_data"


def test_rejects_invalid_window_times_or_inactivity_duration():
    start = datetime(2030, 1, 1, 10, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        analyze_activity(
            [ActivitySignals(start.replace(tzinfo=None), start + timedelta(minutes=1))],
            fusion_config(),
        )
    with pytest.raises(ValueError, match="fit inside"):
        analyze_activity(
            [
                ActivitySignals(
                    start,
                    start + timedelta(minutes=1),
                    inactivity_seconds=61,
                )
            ],
            fusion_config(),
        )
