import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from cv.config import CLASSROOM_ID, LECTURE_ID

EventType = Literal["ENTRY", "EXIT"]


class EventSender:
    def __init__(self, output_path: Path | None = None) -> None:
        self.output_path = output_path or (
            Path(__file__).resolve().parent / "data" / "events.jsonl"
        )

    def send(
        self,
        track_id: int,
        event_type: EventType,
        confidence: float,
        student_id: str = "UNKNOWN",
    ) -> dict[str, str | float | bool]:
        if event_type not in ("ENTRY", "EXIT"):
            raise ValueError("event_type must be ENTRY or EXIT")
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        if not student_id:
            raise ValueError("student_id must not be empty")
        flagged_for_review = student_id == "UNKNOWN"

        event: dict[str, str | float | bool] = {
            "student_id": student_id,
            "flagged_for_review": flagged_for_review,
            "classroom_id": CLASSROOM_ID,
            "lecture_id": LECTURE_ID,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "confidence": confidence,
            "source": "camera",
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as event_file:
            event_file.write(json.dumps(event) + "\n")

        review_status = " (flagged for review)" if flagged_for_review else ""
        print(f"{event_type} track_id={track_id} student_id={student_id}{review_status}")
        return event
