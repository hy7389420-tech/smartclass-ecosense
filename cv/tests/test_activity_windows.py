import json
from datetime import datetime, timedelta, timezone

import pytest

from audio.audio_features import AudioWindowResult
from cv.activity_windows import ActivityWindowWriter, create_activity_window_record
from cv.headpose import HeadPoseWindowResult
from cv.motion import MotionWindowResult


def make_window_results(
    front_facing_ratio: float | None = 0.75,
    audio: AudioWindowResult | None = AudioWindowResult(-25.0, -10.0, 0.4),
) -> tuple[MotionWindowResult, HeadPoseWindowResult, AudioWindowResult | None]:
    return (
        MotionWindowResult(
            movement_level=0.3,
            inactivity_seconds=60.0,
            peak_movement=0.8,
        ),
        HeadPoseWindowResult(
            faces_detected_mean=4.0,
            front_facing_ratio=front_facing_ratio,
        ),
        audio,
    )


def test_record_contains_expected_fields_and_iso_window_boundaries() -> None:
    window_start = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
    window_end = window_start + timedelta(minutes=5)
    motion, head_pose, audio = make_window_results()

    record = create_activity_window_record(
        window_start,
        window_end,
        motion,
        head_pose,
        audio,
        classroom_id="ROOM_1",
        lecture_id="LECTURE_1",
    )

    assert record == {
        "window_start": "2026-10-24T10:00:00+00:00",
        "window_end": "2026-10-24T10:05:00+00:00",
        "classroom_id": "ROOM_1",
        "lecture_id": "LECTURE_1",
        "movement_level": 0.3,
        "inactivity_seconds": 60.0,
        "front_facing_ratio": 0.75,
        "audio_level_db_mean": -25.0,
        "voice_activity_ratio": 0.4,
        "source": "camera+mic",
        "estimate_note": "estimate based on observable indicators",
    }


def test_null_values_for_no_faces_and_unavailable_audio_are_preserved() -> None:
    motion, head_pose, _ = make_window_results(front_facing_ratio=None, audio=None)
    window_start = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)

    record = create_activity_window_record(
        window_start,
        window_start + timedelta(minutes=5),
        motion,
        head_pose,
        None,
    )

    assert record["front_facing_ratio"] is None
    assert record["audio_level_db_mean"] is None
    assert record["voice_activity_ratio"] is None


def test_writer_appends_each_window_as_jsonl(tmp_path) -> None:
    output_path = tmp_path / "data" / "activity_windows.jsonl"
    writer = ActivityWindowWriter(output_path)
    motion, head_pose, audio = make_window_results()
    window_start = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)

    first = writer.write(
        window_start,
        window_start + timedelta(minutes=5),
        motion,
        head_pose,
        audio,
    )
    second = writer.write(
        window_start + timedelta(minutes=5),
        window_start + timedelta(minutes=10),
        motion,
        head_pose,
        audio,
    )

    saved_records = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert saved_records == [first, second]
    assert len(saved_records) == 2


def test_naive_datetime_boundaries_are_rejected() -> None:
    window_start = datetime(2026, 10, 24, 10, 0)
    motion, head_pose, audio = make_window_results()

    with pytest.raises(ValueError, match="timezone"):
        create_activity_window_record(
            window_start,
            window_start + timedelta(minutes=5),
            motion,
            head_pose,
            audio,
        )


def test_invalid_window_duration_is_rejected() -> None:
    window_start = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
    motion, head_pose, audio = make_window_results()

    with pytest.raises(ValueError, match="after"):
        create_activity_window_record(
            window_start,
            window_start,
            motion,
            head_pose,
            audio,
        )
