from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray
from ultralytics import YOLO

from cv.config import DETECTION_CONFIDENCE, YOLO_MODEL

Detection: TypeAlias = tuple[int, int, int, int, float]


class PersonDetector:
    def __init__(
        self,
        model_path: str = YOLO_MODEL,
        confidence: float = DETECTION_CONFIDENCE,
    ) -> None:
        self.model = YOLO(model_path)
        self.confidence = confidence

    def detect(self, frame: NDArray[np.uint8]) -> list[Detection]:
        results = self.model.predict(
            source=frame,
            classes=[0],
            conf=self.confidence,
            verbose=False,
        )
        boxes = results[0].boxes
        if boxes is None:
            return []

        detections: list[Detection] = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf[0].item())
            detections.append(
                (int(x1), int(y1), int(x2), int(y2), confidence)
            )
        return detections
