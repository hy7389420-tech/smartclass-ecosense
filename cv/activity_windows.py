import json
import math
from datetime import datetime
from pathlib import Path

from audio.audio_features import AudioWindowResult
from cv.config import (
    ACTIVITY_ESTIMATE_NOTE,
    ACTIVITY_SOURCE,
    CLASSROOM_ID,
    LECTURE_ID,
)
from cv.headpose import HeadPoseWindowResult
from cv.motion import MotionWindowResult

ActivityWindowRecord = dict[str, str | float | None]


def create_activity_window_record(
    window_start: datetime,
    window_end: datetime,
    motion: MotionWindowResult,
    head_pose: HeadPoseWindowResult,
    audio: AudioWindowResult | None,
    classroom_id: str = CLASSROOM_ID,
    lecture_id: str = LECTURE_ID,
) -> ActivityWindowRecord:
    if window_start.tzinfo is None or window_start.utcoffset() is None:
        raise ValueError("window_start must include a timezone")
    if window_end.tzinfo is None or window_end.utcoffset() is None:
        raise ValueError("window_end must include a timezone")
    duration_seconds = (window_end - window_start).total_seconds()
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("window_end must be after window_start")
    if not classroom_id or not lecture_id:
        raise ValueError("classroom_id and lecture_id must not be empty")
    if not math.isfinite(motion.movement_level) or not 0.0 <= motion.movement_level <= 1.0:
        raise ValueError("movement_level must be finite and between 0 and 1")
    if (
        not math.isfinite(motion.inactivity_seconds)
        or not 0.0 <= motion.inactivity_seconds <= duration_seconds
    ):
        raise ValueError("inactivity_seconds must fit within the window")
    if not math.isfinite(motion.peak_movement) or not 0.0 <= motion.peak_movement <= 1.0:
        raise ValueError("peak_movement must be finite and between 0 and 1")
    if head_pose.front_facing_ratio is not None and (
        not math.isfinite(head_pose.front_facing_ratio)
        or not 0.0 <= head_pose.front_facing_ratio <= 1.0
    ):
        raise ValueError("front_facing_ratio must be null or between 0 and 1")
    if (
        not math.isfinite(head_pose.faces_detected_mean)
        or head_pose.faces_detected_mean < 0.0
    ):
        raise ValueError("faces_detected_mean must be finite and non-negative")
    if audio is not None and (
        not math.isfinite(audio.audio_level_db_mean)
        or not math.isfinite(audio.audio_level_db_peak)
        or audio.audio_level_db_peak > 0.0
        or audio.audio_level_db_mean > 0.0
        or not 0.0 <= audio.voice_activity_ratio <= 1.0
    ):
        raise ValueError("audio results must contain valid dBFS levels and ratio")

    return {
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "classroom_id": classroom_id,
        "lecture_id": lecture_id,
        "movement_level": motion.movement_level,
        "inactivity_seconds": motion.inactivity_seconds,
        "front_facing_ratio": head_pose.front_facing_ratio,
        "audio_level_db_mean": (
            audio.audio_level_db_mean if audio is not None else None
        ),
        "voice_activity_ratio": (
            audio.voice_activity_ratio if audio is not None else None
        ),
        "source": ACTIVITY_SOURCE,
        "estimate_note": ACTIVITY_ESTIMATE_NOTE,
    }


class ActivityWindowWriter:
    def __init__(self, output_path: Path | None = None) -> None:
        self.output_path = output_path or (
            Path(__file__).resolve().parent / "data" / "activity_windows.jsonl"
        )

    def write(
        self,
        window_start: datetime,
        window_end: datetime,
        motion: MotionWindowResult,
        head_pose: HeadPoseWindowResult,
        audio: AudioWindowResult | None,
        classroom_id: str = CLASSROOM_ID,
        lecture_id: str = LECTURE_ID,
    ) -> ActivityWindowRecord:
        record = create_activity_window_record(
            window_start,
            window_end,
            motion,
            head_pose,
            audio,
            classroom_id,
            lecture_id,
        )
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as output_file:
            output_file.write(json.dumps(record, allow_nan=False) + "\n")
        return record
