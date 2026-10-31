import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class MotionWorkspace:
    difference: np.ndarray
    changed_mask: np.ndarray

    @classmethod
    def for_shape(cls, shape: tuple[int, int]) -> "MotionWorkspace":
        if len(shape) != 2 or any(dimension <= 0 for dimension in shape):
            raise ValueError("shape must contain two positive dimensions")
        return cls(
            difference=np.empty(shape, dtype=np.int16),
            changed_mask=np.empty(shape, dtype=np.bool_),
        )


@dataclass(frozen=True)
class MotionWindowResult:
    movement_level: float
    inactivity_seconds: float
    peak_movement: float


def compute_motion_score(
    previous_gray: np.ndarray,
    current_gray: np.ndarray,
    pixel_change_threshold: int,
    workspace: MotionWorkspace | None = None,
) -> float:
    previous = np.asarray(previous_gray)
    current = np.asarray(current_gray)
    if (
        previous.ndim != 2
        or current.ndim != 2
        or previous.size == 0
        or current.size == 0
        or previous.shape != current.shape
    ):
        raise ValueError("frames must be non-empty grayscale arrays of equal shape")
    if previous.dtype != np.uint8 or current.dtype != np.uint8:
        raise ValueError("grayscale frames must use uint8 pixels")
    if (
        not isinstance(pixel_change_threshold, int)
        or not 0 <= pixel_change_threshold <= 255
    ):
        raise ValueError("pixel_change_threshold must be an integer from 0 to 255")

    if workspace is None:
        workspace = MotionWorkspace.for_shape(previous.shape)
    if (
        workspace.difference.shape != previous.shape
        or workspace.difference.dtype != np.int16
        or workspace.changed_mask.shape != previous.shape
        or workspace.changed_mask.dtype != np.bool_
    ):
        raise ValueError("workspace arrays must match the grayscale frame shape")

    np.subtract(
        current,
        previous,
        out=workspace.difference,
        dtype=np.int16,
    )
    np.abs(workspace.difference, out=workspace.difference)
    np.greater(
        workspace.difference,
        pixel_change_threshold,
        out=workspace.changed_mask,
    )
    return float(np.count_nonzero(workspace.changed_mask) / previous.size)


def aggregate_motion_window(
    samples: Sequence[tuple[float, float]],
    window_start: float,
    window_end: float,
    inactivity_threshold: float,
    max_sample_gap_seconds: float,
) -> MotionWindowResult:
    if (
        not math.isfinite(window_start)
        or not math.isfinite(window_end)
        or window_end <= window_start
    ):
        raise ValueError("window boundaries must be finite and end after start")
    if (
        not math.isfinite(inactivity_threshold)
        or not 0.0 <= inactivity_threshold <= 1.0
    ):
        raise ValueError("inactivity_threshold must be between 0 and 1")
    if (
        not math.isfinite(max_sample_gap_seconds)
        or max_sample_gap_seconds <= 0
    ):
        raise ValueError("max_sample_gap_seconds must be finite and greater than 0")
    if not samples:
        raise ValueError("samples must not be empty")

    previous_timestamp: float | None = None
    movement_total = 0.0
    peak_movement = 0.0
    inactivity_seconds = 0.0

    for index, (timestamp, score) in enumerate(samples):
        if not math.isfinite(timestamp) or not window_start <= timestamp <= window_end:
            raise ValueError("sample timestamps must be finite and inside the window")
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError("motion scores must be finite and between 0 and 1")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise ValueError("sample timestamps must be strictly increasing")

        movement_total += score
        peak_movement = max(peak_movement, score)
        interval_end = (
            samples[index + 1][0] if index + 1 < len(samples) else window_end
        )
        interval_seconds = interval_end - timestamp
        if (
            score < inactivity_threshold
            and 0.0 < interval_seconds <= max_sample_gap_seconds
        ):
            inactivity_seconds += interval_seconds
        previous_timestamp = timestamp

    return MotionWindowResult(
        movement_level=movement_total / len(samples),
        inactivity_seconds=inactivity_seconds,
        peak_movement=peak_movement,
    )
