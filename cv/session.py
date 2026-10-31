import math
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

import numpy as np

from audio.audio_capture import MicrophoneCapture
from audio.audio_features import AudioWindowResult
from cv.activity_windows import ActivityWindowWriter
from cv.config import (
    ACTIVITY_WINDOW_SECONDS,
    CAMERA_INDEX,
    HEAD_POSE_FRONT_DEGREES,
    INACTIVITY_THRESHOLD,
    MOTION_MAX_SAMPLE_GAP_SECONDS,
)
from cv.headpose import (
    HeadPoseWindowResult,
    aggregate_headpose_window,
)
from cv.headpose_capture import HeadPoseEstimator
from cv.motion import aggregate_motion_window
from cv.motion_capture import FrameMotionScorer


class ActivitySession:
    def __init__(
        self,
        window_seconds: float = ACTIVITY_WINDOW_SECONDS,
        motion_scorer_factory: Callable[[], FrameMotionScorer] = FrameMotionScorer,
        head_pose_factory: Callable[[], HeadPoseEstimator] = HeadPoseEstimator,
        microphone_factory: Callable[[], MicrophoneCapture] = MicrophoneCapture,
        writer: ActivityWindowWriter | None = None,
    ) -> None:
        if not math.isfinite(window_seconds) or window_seconds <= 0.0:
            raise ValueError("window_seconds must be finite and greater than 0")

        self.window_seconds = window_seconds
        self._motion_scorer_factory = motion_scorer_factory
        self._head_pose_factory = head_pose_factory
        self._microphone_factory = microphone_factory
        self._writer = writer or ActivityWindowWriter()
        self._motion_scorer: FrameMotionScorer | None = None
        self._head_pose: HeadPoseEstimator | None = None
        self._microphone: MicrophoneCapture | None = None
        self._window_start_monotonic: float | None = None
        self._window_start_datetime: datetime | None = None
        self._motion_samples: list[tuple[float, float]] = []
        self._head_pose_samples: list[list[float]] = []
        self._last_timestamp: float | None = None
        self._started = False
        self._finished = False
        self._closed = False

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("activity session is closed")
        if self._started:
            raise RuntimeError("activity session is already started")

        self._window_start_monotonic = time.monotonic()
        self._window_start_datetime = datetime.now(timezone.utc)
        self._motion_scorer = self._motion_scorer_factory()
        self._head_pose = self._head_pose_factory()
        self._microphone = self._microphone_factory()
        self._microphone.start()
        self._started = True

    def process_frame(self, frame: np.ndarray, timestamp: float) -> None:
        if not self._started or self._closed or self._finished:
            raise RuntimeError("activity session is not active")
        if not math.isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        assert self._window_start_monotonic is not None
        if timestamp < self._window_start_monotonic:
            raise ValueError("timestamp must not precede the activity session")
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError("frame timestamps must be strictly increasing")
        self._last_timestamp = timestamp

        while timestamp >= self._window_start_monotonic + self.window_seconds:
            window_end = self._window_start_monotonic + self.window_seconds
            self._write_window(window_end)
            self._advance_window()

        assert self._motion_scorer is not None
        assert self._head_pose is not None
        motion_score = self._motion_scorer.score(frame)
        if motion_score is not None:
            self._motion_samples.append((timestamp, motion_score))

        frame_timestamp_ms = round(timestamp * 1000)
        head_pose_yaws = self._head_pose.process_frame(frame, frame_timestamp_ms)
        if head_pose_yaws is not None:
            self._head_pose_samples.append(head_pose_yaws)

    def finish(self, timestamp: float) -> None:
        if not self._started or self._closed or self._finished:
            return
        if not math.isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        assert self._window_start_monotonic is not None
        if timestamp < self._window_start_monotonic:
            raise ValueError("timestamp must not precede the activity session")

        while timestamp >= self._window_start_monotonic + self.window_seconds:
            window_end = self._window_start_monotonic + self.window_seconds
            self._write_window(window_end)
            self._advance_window()
        self._write_window(timestamp)
        self._finished = True

    def _write_window(self, window_end_monotonic: float) -> None:
        assert self._window_start_monotonic is not None
        assert self._window_start_datetime is not None
        assert self._microphone is not None
        if window_end_monotonic <= self._window_start_monotonic:
            return

        audio_result: AudioWindowResult | None = self._microphone.read_window(
            self._window_start_monotonic,
            window_end_monotonic,
        )
        if not self._motion_samples:
            self._head_pose_samples.clear()
            return

        motion_result = aggregate_motion_window(
            samples=self._motion_samples,
            window_start=self._window_start_monotonic,
            window_end=window_end_monotonic,
            inactivity_threshold=INACTIVITY_THRESHOLD,
            max_sample_gap_seconds=MOTION_MAX_SAMPLE_GAP_SECONDS,
        )
        head_pose_result = (
            aggregate_headpose_window(
                self._head_pose_samples,
                HEAD_POSE_FRONT_DEGREES,
            )
            if self._head_pose_samples
            else HeadPoseWindowResult(
                faces_detected_mean=0.0,
                front_facing_ratio=None,
            )
        )
        window_duration = window_end_monotonic - self._window_start_monotonic
        window_end_datetime = self._window_start_datetime + timedelta(
            seconds=window_duration
        )
        self._writer.write(
            window_start=self._window_start_datetime,
            window_end=window_end_datetime,
            motion=motion_result,
            head_pose=head_pose_result,
            audio=audio_result,
        )
        self._motion_samples.clear()
        self._head_pose_samples.clear()

    def _advance_window(self) -> None:
        assert self._window_start_monotonic is not None
        assert self._window_start_datetime is not None
        self._window_start_monotonic += self.window_seconds
        self._window_start_datetime += timedelta(seconds=self.window_seconds)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._microphone is not None:
            try:
                self._microphone.close()
            finally:
                if self._head_pose is not None:
                    self._head_pose.close()
        elif self._head_pose is not None:
            self._head_pose.close()


def run_session(camera_index: int = CAMERA_INDEX) -> None:
    from cv.capture import run_camera

    analytics = ActivitySession()
    run_camera(camera_index=camera_index, analytics=analytics)


def main() -> None:
    run_session()


if __name__ == "__main__":
    main()
