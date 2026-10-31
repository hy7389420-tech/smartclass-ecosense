import time
from typing import Protocol

import numpy as np
import cv2

from cv.config import (
    CAMERA_INDEX,
    DEMO_STUDENTS,
    LINE_CROSSING_COOLDOWN_SECONDS,
    LINE_CROSSING_HYSTERESIS_DISTANCE,
    LINE_END,
    LINE_START,
    MAX_GAP_SECONDS,
    MIN_CONFIDENCE,
    MIN_PRESENCE_SECONDS,
    WINDOW_NAME,
)
from cv.detector import PersonDetector
from cv.event_sender import EventSender
from cv.identity import IdentityMapper
from cv.line_counter import LineCounter
from cv.sustained import SustainedPresence
from cv.tracker import PersonTracker


class FrameAnalytics(Protocol):
    def start(self) -> None: ...

    def process_frame(self, frame: np.ndarray, timestamp: float) -> None: ...

    def finish(self, timestamp: float) -> None: ...

    def close(self) -> None: ...


def run_camera(
    camera_index: int = CAMERA_INDEX,
    analytics: FrameAnalytics | None = None,
) -> None:
    camera = cv2.VideoCapture(camera_index)

    if not camera.isOpened():
        camera.release()
        print("Camera Offline")
        return

    analytics_started = False
    try:
        if analytics is not None:
            analytics_started = True
            analytics.start()

        detector = PersonDetector()
        tracker = PersonTracker(detector.model)
        identity_mapper = IdentityMapper(DEMO_STUDENTS)
        line_counter = LineCounter(
            LINE_START,
            LINE_END,
            LINE_CROSSING_COOLDOWN_SECONDS,
            LINE_CROSSING_HYSTERESIS_DISTANCE,
        )
        sustained_presence = SustainedPresence(
            MIN_PRESENCE_SECONDS,
            MIN_CONFIDENCE,
            MAX_GAP_SECONDS,
        )
        event_sender = EventSender()
        selection = {"track_id": None, "boxes": []}

        def select_track(event: int, x: int, y: int, flags: int, data: object) -> None:
            if event != cv2.EVENT_LBUTTONDOWN:
                return
            for x1, y1, x2, y2, track_id in reversed(selection["boxes"]):
                if x1 <= x <= x2 and y1 <= y <= y2:
                    selection["track_id"] = track_id
                    print(f"Selected track_id={track_id}")
                    return
            selection["track_id"] = None

        cv2.namedWindow(WINDOW_NAME)
        cv2.setMouseCallback(WINDOW_NAME, select_track)
        while True:
            success, frame = camera.read()
            if not success:
                print("Camera Offline")
                break

            frame_timestamp = time.monotonic()
            if analytics is not None:
                analytics.process_frame(frame, frame_timestamp)

            frame_height, frame_width = frame.shape[:2]
            line_start = (
                int(LINE_START[0] * frame_width),
                int(LINE_START[1] * frame_height),
            )
            line_end = (
                int(LINE_END[0] * frame_width),
                int(LINE_END[1] * frame_height),
            )
            cv2.line(frame, line_start, line_end, (0, 0, 255), 2)

            detections = tracker.track(frame)
            selection["boxes"] = [
                (x1, y1, x2, y2, track_id)
                for x1, y1, x2, y2, _, track_id in detections
            ]
            if selection["track_id"] not in {
                track_id for _, _, _, _, track_id in selection["boxes"]
            }:
                selection["track_id"] = None
            for x1, y1, x2, y2, confidence, track_id in detections:
                presence_confirmed = sustained_presence.update(
                    track_id,
                    frame_timestamp,
                    confidence,
                )
                identity = identity_mapper.get(track_id)
                is_selected = selection["track_id"] == track_id
                color = (255, 255, 0) if is_selected else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                review_status = " (review)" if identity.flagged_for_review else ""
                cv2.putText(
                    frame,
                    f"Person ID {track_id} - {identity.name}{review_status}",
                    (x1, max(y1 - 10, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )

                bottom_center = ((x1 + x2) / 2, y2)
                crossing = line_counter.update(
                    track_id,
                    (
                        bottom_center[0] / frame_width,
                        bottom_center[1] / frame_height,
                    ),
                    frame_timestamp,
                )
                if crossing is not None and presence_confirmed:
                    identity = identity_mapper.get(crossing.track_id)
                    event_sender.send(
                        crossing.track_id,
                        crossing.event_type,
                        confidence,
                        student_id=identity.student_id,
                    )

            cv2.putText(
                frame,
                "Click a person, press 1-5 to assign, q to quit",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )
            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if ord("1") <= key <= ord("5"):
                selected_track_id = selection["track_id"]
                if selected_track_id is None:
                    print("Select a person box before assigning a student")
                    continue
                identity = identity_mapper.assign(
                    selected_track_id,
                    chr(key),
                )
                print(
                    f"Assigned track_id={selected_track_id} "
                    f"to {identity.name} ({identity.student_id})"
                )
    finally:
        try:
            if analytics_started and analytics is not None:
                analytics.finish(time.monotonic())
        finally:
            try:
                if analytics_started and analytics is not None:
                    analytics.close()
            finally:
                camera.release()
                cv2.destroyAllWindows()


if __name__ == "__main__":
    run_camera()
