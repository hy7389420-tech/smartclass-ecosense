from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray
from ultralytics import YOLO

from cv.config import BYTE_TRACKER, DETECTION_CONFIDENCE

TrackedDetection: TypeAlias = tuple[int, int, int, int, float, int]


class PersonTracker:
    def __init__(self, model: YOLO) -> None:
        self.model = model

    def track(self, frame: NDArray[np.uint8]) -> list[TrackedDetection]:
        results = self.model.track(
            source=frame,
            persist=True,
            tracker=BYTE_TRACKER,
            classes=[0],
            conf=DETECTION_CONFIDENCE,
            verbose=False,
        )
        boxes = results[0].boxes
        if boxes is None or boxes.id is None:
            return []

        tracked_detections: list[TrackedDetection] = []
        for index, box in enumerate(boxes):
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf[0].item())
            track_id = int(boxes.id[index].item())
            tracked_detections.append(
                (int(x1), int(y1), int(x2), int(y2), confidence, track_id)
            )
        return tracked_detections
