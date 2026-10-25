from datetime import UTC, datetime, timedelta

import pytest

from app.services.anomaly import ExitEvent, detect_exit_spikes


def test_detects_exit_spike_in_five_minute_bucket():
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    events = [
        ExitEvent(start + timedelta(minutes=25, seconds=second)) for second in range(7)
    ]

    spikes = detect_exit_spikes(
        events, start, start + timedelta(minutes=60), min_buckets=3
    )

    assert len(spikes) == 1
    assert spikes[0].start == start + timedelta(minutes=25)
    assert spikes[0].end == start + timedelta(minutes=30)
    assert spikes[0].exit_count == 7


def test_flat_exit_activity_and_too_few_buckets_do_not_flag():
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    flat_events = [
        ExitEvent(start + timedelta(minutes=window * 5, seconds=second))
        for window in range(12)
        for second in range(3)
    ]

    assert detect_exit_spikes(flat_events, start, start + timedelta(minutes=60)) == ()
    assert (
        detect_exit_spikes(
            [ExitEvent(start)],
            start,
            start + timedelta(minutes=10),
            min_buckets=3,
        )
        == ()
    )


def test_anomaly_detection_rejects_invalid_times_and_thresholds():
    start = datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="must include a timezone"):
        detect_exit_spikes(
            [], start.replace(tzinfo=None), start + timedelta(minutes=10)
        )
    with pytest.raises(ValueError, match="must be after"):
        detect_exit_spikes([], start, start)
    with pytest.raises(ValueError, match="window_minutes must be positive"):
        detect_exit_spikes([], start, start + timedelta(minutes=10), window_minutes=0)
