import cv2
import numpy as np

from cv.config import (
    MOTION_BLUR_KERNEL_SIZE,
    MOTION_FRAME_HEIGHT,
    MOTION_FRAME_WIDTH,
    MOTION_PIXEL_CHANGE_THRESHOLD,
)
from cv.motion import MotionWorkspace, compute_motion_score


class FrameMotionScorer:
    def __init__(
        self,
        frame_width: int = MOTION_FRAME_WIDTH,
        frame_height: int = MOTION_FRAME_HEIGHT,
        blur_kernel_size: int = MOTION_BLUR_KERNEL_SIZE,
        pixel_change_threshold: int = MOTION_PIXEL_CHANGE_THRESHOLD,
    ) -> None:
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("frame dimensions must be positive")
        if blur_kernel_size <= 0 or blur_kernel_size % 2 == 0:
            raise ValueError("blur_kernel_size must be a positive odd integer")
        if (
            not isinstance(pixel_change_threshold, int)
            or not 0 <= pixel_change_threshold <= 255
        ):
            raise ValueError("pixel_change_threshold must be an integer from 0 to 255")

        self.frame_width = frame_width
        self.frame_height = frame_height
        self.blur_kernel_size = blur_kernel_size
        self.pixel_change_threshold = pixel_change_threshold
        self._input_shape: tuple[int, ...] | None = None
        self._gray: np.ndarray | None = None
        self._blurred: np.ndarray | None = None
        self._current_small: np.ndarray | None = None
        self._previous_small: np.ndarray | None = None
        self._workspace = MotionWorkspace.for_shape((frame_height, frame_width))

    def score(self, frame: np.ndarray) -> float | None:
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            raise ValueError("frame must be a non-empty NumPy array")
        if frame.dtype != np.uint8:
            raise ValueError("frame must use uint8 pixels")
        if frame.ndim == 2:
            height, width = frame.shape
        elif frame.ndim == 3 and frame.shape[2] == 3:
            height, width = frame.shape[:2]
        else:
            raise ValueError("frame must be grayscale or a three-channel BGR image")

        if self._input_shape != frame.shape:
            self._input_shape = frame.shape
            self._gray = np.empty((height, width), dtype=np.uint8)
            self._blurred = np.empty((height, width), dtype=np.uint8)
            self._current_small = np.empty(
                (self.frame_height, self.frame_width),
                dtype=np.uint8,
            )
            self._previous_small = None

        if frame.ndim == 2:
            np.copyto(self._gray, frame)
        else:
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY, dst=self._gray)
        cv2.GaussianBlur(
            self._gray,
            (self.blur_kernel_size, self.blur_kernel_size),
            0,
            dst=self._blurred,
        )
        cv2.resize(
            self._blurred,
            (self.frame_width, self.frame_height),
            dst=self._current_small,
            interpolation=cv2.INTER_AREA,
        )

        if self._previous_small is None:
            self._previous_small = self._current_small.copy()
            return None

        score = compute_motion_score(
            self._previous_small,
            self._current_small,
            self.pixel_change_threshold,
            self._workspace,
        )
        np.copyto(self._previous_small, self._current_small)
        return score
