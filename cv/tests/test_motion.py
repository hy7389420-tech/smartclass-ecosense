import numpy as np
import pytest

from cv.motion import (
    MotionWorkspace,
    aggregate_motion_window,
    compute_motion_score,
)
from cv.motion_capture import FrameMotionScorer


def test_identical_frames_have_zero_motion() -> None:
    frame = np.zeros((64, 64), dtype=np.uint8)

    assert compute_motion_score(frame, frame.copy(), 25) == 0.0


def test_changed_frames_have_high_motion() -> None:
    previous = np.zeros((64, 64), dtype=np.uint8)
    current = previous.copy()
    current[16:48, 16:48] = 255

    score = compute_motion_score(previous, current, 25)

    assert score == pytest.approx(0.25)


def test_motion_score_reuses_workspace_without_changing_frames() -> None:
    previous = np.zeros((8, 8), dtype=np.uint8)
    current = np.full((8, 8), 255, dtype=np.uint8)
    previous_before = previous.copy()
    current_before = current.copy()
    workspace = MotionWorkspace.for_shape(previous.shape)

    assert compute_motion_score(previous, current, 25, workspace) == 1.0
    assert np.array_equal(previous, previous_before)
    assert np.array_equal(current, current_before)


def test_motion_window_aggregates_mean_peak_and_inactivity_duration() -> None:
    result = aggregate_motion_window(
        samples=[(0.0, 0.0), (1.0, 0.005), (2.0, 0.4), (3.0, 0.0)],
        window_start=0.0,
        window_end=4.0,
        inactivity_threshold=0.01,
        max_sample_gap_seconds=1.0,
    )

    assert result.movement_level == pytest.approx(0.10125)
    assert result.inactivity_seconds == pytest.approx(3.0)
    assert result.peak_movement == pytest.approx(0.4)


def test_large_sample_gap_is_not_counted_as_inactivity() -> None:
    result = aggregate_motion_window(
        samples=[(0.0, 0.0), (2.0, 0.0)],
        window_start=0.0,
        window_end=3.0,
        inactivity_threshold=0.01,
        max_sample_gap_seconds=1.0,
    )

    assert result.inactivity_seconds == pytest.approx(1.0)


def test_empty_motion_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        aggregate_motion_window([], 0.0, 10.0, 0.01, 1.0)


def test_frame_scorer_preprocesses_fake_frames_and_skips_first_baseline() -> None:
    scorer = FrameMotionScorer()
    still_frame = np.zeros((128, 128, 3), dtype=np.uint8)
    changed_frame = still_frame.copy()
    changed_frame[:, 64:] = 255

    assert scorer.score(still_frame) is None
    assert scorer.score(still_frame.copy()) == 0.0
    assert scorer.score(changed_frame) > 0.4

