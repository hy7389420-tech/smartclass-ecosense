import math
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from cv.config import (
    HEAD_POSE_FRAME_SKIP,
    HEAD_POSE_MAX_FACES,
    HEAD_POSE_MAX_FRAME_WIDTH,
    HEAD_POSE_MIN_FACE_DETECTION_CONFIDENCE,
    HEAD_POSE_MIN_FACE_PRESENCE_CONFIDENCE,
    HEAD_POSE_MIN_TRACKING_CONFIDENCE,
    HEAD_POSE_MODEL_PATH,
)
from cv.headpose import yaw_degrees_from_transformation_matrix


class HeadPoseEstimator:
    def __init__(
        self,
        model_path: Path = HEAD_POSE_MODEL_PATH,
        frame_skip: int = HEAD_POSE_FRAME_SKIP,
        max_faces: int = HEAD_POSE_MAX_FACES,
        max_frame_width: int = HEAD_POSE_MAX_FRAME_WIDTH,
        min_face_detection_confidence: float = (
            HEAD_POSE_MIN_FACE_DETECTION_CONFIDENCE
        ),
        min_face_presence_confidence: float = HEAD_POSE_MIN_FACE_PRESENCE_CONFIDENCE,
        min_tracking_confidence: float = HEAD_POSE_MIN_TRACKING_CONFIDENCE,
    ) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(f"Face Landmarker model not found: {model_path}")
        if frame_skip <= 0 or max_faces <= 0 or max_frame_width <= 0:
            raise ValueError(
                "frame_skip, max_faces, and max_frame_width must be positive"
            )
        for name, value in (
            ("min_face_detection_confidence", min_face_detection_confidence),
            ("min_face_presence_confidence", min_face_presence_confidence),
            ("min_tracking_confidence", min_tracking_confidence),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")

        self.frame_skip = frame_skip
        self.max_frame_width = max_frame_width
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=max_faces,
            min_face_detection_confidence=min_face_detection_confidence,
            min_face_presence_confidence=min_face_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        self._frame_index = 0
        self._last_timestamp_ms: int | None = None

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp_ms: int,
    ) -> list[float] | None:
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            raise ValueError("frame must be a non-empty NumPy array")
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must be a three-channel uint8 BGR image")
        if not isinstance(timestamp_ms, int) or timestamp_ms < 0:
            raise ValueError("timestamp_ms must be a non-negative integer")
        if (
            self._last_timestamp_ms is not None
            and timestamp_ms <= self._last_timestamp_ms
        ):
            raise ValueError("timestamp_ms must be strictly increasing")
        self._last_timestamp_ms = timestamp_ms
        self._frame_index += 1

        if self._frame_index % self.frame_skip:
            return None

        height, width = frame.shape[:2]
        if width > self.max_frame_width:
            resized_height = max(1, round(height * self.max_frame_width / width))
            frame = cv2.resize(
                frame,
                (self.max_frame_width, resized_height),
                interpolation=cv2.INTER_AREA,
            )
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        matrices = result.facial_transformation_matrixes
        if len(matrices) != len(result.face_landmarks):
            raise RuntimeError(
                "MediaPipe did not return one pose matrix per detected face"
            )

        return [
            yaw_degrees_from_transformation_matrix(matrix.tolist())
            for matrix in matrices
        ]

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self) -> "HeadPoseEstimator":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()
