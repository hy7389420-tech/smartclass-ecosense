import json
from datetime import datetime

import numpy as np
import pytest

from audio.audio_features import AudioWindowResult
from cv.activity_windows import ActivityWindowWriter
from cv.capture import run_camera
from cv.session import ActivitySession


class FakeMotionScorer:
    def __init__(self) -> None:
        self._scores: list[float | None] = [None, 0.2, 0.0]

    def score(self, frame: np.ndarray) -> float | None:
        return self._scores.pop(0)


class FakeHeadPoseEstimator:
    def process_frame(
        self,
        frame: np.ndarray,
        timestamp_ms: int,
    ) -> list[float] | None:
        return [] if timestamp_ms >= 102_000 else None

    def close(self) -> None:
        return None


class FakeMicrophone:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.closed = False

    def start(self) -> bool:
        return self.available

    def read_window(
        self,
        window_start: float,
        window_end: float,
    ) -> AudioWindowResult | None:
        if not self.available:
            return None
        return AudioWindowResult(-25.0, -10.0, 0.4)

    def close(self) -> None:
        self.closed = True


def make_activity_session(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    microphone: FakeMicrophone,
) -> ActivitySession:
    monkeypatch.setattr("cv.session.time.monotonic", lambda: 100.0)
    return ActivitySession(
        window_seconds=10.0,
        motion_scorer_factory=FakeMotionScorer,
        head_pose_factory=FakeHeadPoseEstimator,
        microphone_factory=lambda: microphone,
        writer=ActivityWindowWriter(tmp_path / "activity_windows.jsonl"),
    )


def test_session_writes_partial_window_and_closes_devices(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    microphone = FakeMicrophone()
    session = make_activity_session(tmp_path, monkeypatch, microphone)
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    session.start()
    session.process_frame(frame, 100.0)
    session.process_frame(frame, 102.0)
    session.process_frame(frame, 103.0)
    session.finish(105.0)
    session.finish(105.0)
    session.close()

    records = [
        json.loads(line)
        for line in (tmp_path / "activity_windows.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(records) == 1
    assert records[0]["window_end"]
    start = datetime.fromisoformat(records[0]["window_start"])
    end = datetime.fromisoformat(records[0]["window_end"])
    assert (end - start).total_seconds() == pytest.approx(5.0)
    assert records[0]["movement_level"] == pytest.approx(0.1)
    assert records[0]["front_facing_ratio"] is None
    assert records[0]["audio_level_db_mean"] == -25.0
    assert microphone.closed


def test_offline_microphone_keeps_audio_fields_null(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    microphone = FakeMicrophone(available=False)
    session = make_activity_session(tmp_path, monkeypatch, microphone)
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    session.start()
    session.process_frame(frame, 100.0)
    session.process_frame(frame, 102.0)
    session.finish(105.0)
    session.close()

    record = json.loads(
        (tmp_path / "activity_windows.jsonl").read_text(encoding="utf-8")
    )
    assert record["audio_level_db_mean"] is None
    assert record["voice_activity_ratio"] is None


def test_no_motion_samples_does_not_write_fake_activity_window(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    microphone = FakeMicrophone()
    session = make_activity_session(tmp_path, monkeypatch, microphone)

    session.start()
    session.finish(105.0)
    session.close()

    assert not (tmp_path / "activity_windows.jsonl").exists()


def test_camera_offline_does_not_start_analytics_or_create_data(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class OfflineCamera:
        def isOpened(self) -> bool:
            return False

        def release(self) -> None:
            return None

    class NeverStartedAnalytics:
        def start(self) -> None:
            pytest.fail("analytics must not start without a camera")

    monkeypatch.setattr("cv.capture.cv2.VideoCapture", lambda index: OfflineCamera())

    run_camera(analytics=NeverStartedAnalytics())  # type: ignore[arg-type]

    assert capsys.readouterr().out.strip() == "Camera Offline"


def test_q_key_finishes_session_and_releases_camera(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    class OnlineCamera:
        def isOpened(self) -> bool:
            return True

        def read(self) -> tuple[bool, np.ndarray]:
            return True, frame

        def release(self) -> None:
            calls.append("camera_release")

    class FakeDetector:
        model = object()

    class FakeTracker:
        def __init__(self, model: object) -> None:
            return None

        def track(
            self,
            image: np.ndarray,
        ) -> list[tuple[int, int, int, int, float, int]]:
            return []

    class FakeAnalytics:
        def start(self) -> None:
            calls.append("start")

        def process_frame(self, image: np.ndarray, timestamp: float) -> None:
            calls.append("process")

        def finish(self, timestamp: float) -> None:
            calls.append("finish")

        def close(self) -> None:
            calls.append("close")

    monkeypatch.setattr("cv.capture.cv2.VideoCapture", lambda index: OnlineCamera())
    monkeypatch.setattr("cv.capture.PersonDetector", FakeDetector)
    monkeypatch.setattr("cv.capture.PersonTracker", FakeTracker)
    monkeypatch.setattr("cv.capture.cv2.namedWindow", lambda name: None)
    monkeypatch.setattr("cv.capture.cv2.setMouseCallback", lambda name, callback: None)
    monkeypatch.setattr("cv.capture.cv2.imshow", lambda name, image: None)
    monkeypatch.setattr("cv.capture.cv2.waitKey", lambda delay: ord("q"))
    monkeypatch.setattr("cv.capture.cv2.destroyAllWindows", lambda: None)

    run_camera(analytics=FakeAnalytics())  # type: ignore[arg-type]

    assert calls == ["start", "process", "finish", "close", "camera_release"]
