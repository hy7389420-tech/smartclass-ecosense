import json
import math
import os
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
from cv.config import CLASSROOM_ID, LECTURE_ID
from dotenv import load_dotenv

EventType = Literal["ENTRY", "EXIT"]
DELIVERY_ATTEMPTS = 3
DELIVERY_TIMEOUT_SECONDS = 2.0
DELIVERY_BACKOFF_SECONDS = 0.5
DELIVERY_RETRY_POLL_SECONDS = 30.0
MAX_RETRY_AFTER_SECONDS = 30.0


class EventSender:
    def __init__(self, output_path: Path | None = None) -> None:
        self.output_path = output_path or (
            Path(__file__).resolve().parent / "data" / "events.jsonl"
        )
        self.checkpoint_path = self.output_path.with_suffix(".delivery")
        project_root = Path(__file__).resolve().parents[1]
        load_dotenv(project_root / ".env")

        self.api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip(
            "/"
        )
        self.camera_key = os.getenv("ECOSENSE_CAMERA_KEY", "").strip()
        self.classroom_id = self._read_resource_id("CLASSROOM_ID", CLASSROOM_ID)
        self.lecture_id = self._read_resource_id("LECTURE_ID", LECTURE_ID)
        self.retry_attempts = self._read_positive_int(
            "CV_DELIVERY_RETRY_ATTEMPTS", DELIVERY_ATTEMPTS
        )
        self._archive_lock = threading.Lock()
        self._delivery_wake = threading.Event()
        self._delivery_stop = threading.Event()
        self._delivery_blocked = False
        self._delivery_thread: threading.Thread | None = None

        self._initialize_checkpoint()
        if self._delivery_is_configured():
            self._delivery_thread = threading.Thread(
                target=self._deliver_pending_events,
                name="cv-event-delivery",
                daemon=True,
            )
            self._delivery_thread.start()
            self._delivery_wake.set()

    def send(
        self,
        track_id: int,
        event_type: EventType,
        confidence: float,
        student_id: str = "UNKNOWN",
    ) -> dict[str, str | float | bool | int]:
        if event_type not in ("ENTRY", "EXIT"):
            raise ValueError("event_type must be ENTRY or EXIT")
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be finite and between 0 and 1")
        if not student_id:
            raise ValueError("student_id must not be empty")
        flagged_for_review = student_id == "UNKNOWN"

        event: dict[str, str | float | bool | int] = {
            "client_event_id": uuid.uuid4().hex,
            "student_id": student_id,
            "flagged_for_review": flagged_for_review,
            "classroom_id": self.classroom_id,
            "lecture_id": self.lecture_id,
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "confidence": confidence,
            "source": "camera",
            "presence_confirmed": True,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with (
            self._archive_lock,
            self.output_path.open("a", encoding="utf-8") as event_file,
        ):
            event_file.write(json.dumps(event) + "\n")
            event_file.flush()
            os.fsync(event_file.fileno())

        review_status = " (flagged for review)" if flagged_for_review else ""
        print(
            f"{event_type} track_id={track_id} student_id={student_id}{review_status}"
        )
        if self._delivery_is_configured():
            self._delivery_wake.set()
        else:
            print(
                "Backend delivery is not configured; set API_BASE_URL, "
                "ECOSENSE_CAMERA_KEY, CLASSROOM_ID, and LECTURE_ID. Event remains in "
                f"{self.output_path}."
            )
        return event

    def close(self) -> None:
        self._delivery_stop.set()
        self._delivery_wake.set()
        if self._delivery_thread is not None:
            self._delivery_thread.join(timeout=5)

    def _delivery_is_configured(self) -> bool:
        return bool(
            self.camera_key
            and isinstance(self.classroom_id, int)
            and isinstance(self.lecture_id, int)
        )

    def _initialize_checkpoint(self) -> None:
        with self._archive_lock:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            if self.checkpoint_path.exists():
                return
            existing_event_count = 0
            if self.output_path.exists():
                with self.output_path.open(encoding="utf-8") as event_file:
                    existing_event_count = sum(1 for line in event_file if line.strip())
            self._write_checkpoint(existing_event_count)

    def _read_checkpoint(self) -> int:
        try:
            value = int(self.checkpoint_path.read_text(encoding="ascii").strip())
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Cannot read event-delivery checkpoint {self.checkpoint_path}."
            ) from exc
        if value < 0:
            raise RuntimeError(
                f"Event-delivery checkpoint {self.checkpoint_path} is invalid."
            )
        return value

    def _write_checkpoint(self, value: int) -> None:
        temporary_path = self.checkpoint_path.with_name(
            f"{self.checkpoint_path.name}.{uuid.uuid4().hex}.tmp"
        )
        with temporary_path.open("w", encoding="ascii") as checkpoint_file:
            checkpoint_file.write(f"{value}\n")
            checkpoint_file.flush()
            os.fsync(checkpoint_file.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary_path, self.checkpoint_path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05)

    def _deliver_pending_events(self) -> None:
        while not self._delivery_stop.is_set():
            timeout = None if self._delivery_blocked else DELIVERY_RETRY_POLL_SECONDS
            self._delivery_wake.wait(timeout=timeout)
            self._delivery_wake.clear()
            if self._delivery_stop.is_set():
                return
            self._delivery_blocked = False
            if not self._delivery_is_configured():
                continue
            try:
                self._drain_archive()
            except (OSError, RuntimeError, json.JSONDecodeError) as exc:
                print(f"CV event delivery paused: {exc}")

    def _drain_archive(self) -> None:
        with self._archive_lock:
            if not self.output_path.exists():
                return
            checkpoint = self._read_checkpoint()
            with self.output_path.open(encoding="utf-8") as event_file:
                events = [json.loads(line) for line in event_file if line.strip()]

        if checkpoint > len(events):
            print(
                f"Delivery checkpoint {self.checkpoint_path} is ahead of archive "
                f"{self.output_path}. Safe fix: reset the checkpoint to 0 only "
                "after verifying stale events, or remove both delivery files and "
                "restart so the configured lecture can be archived again."
            )
            return

        for index in range(checkpoint, len(events)):
            event = events[index]
            mismatch_reason = self._resource_mismatch_reason(event)
            if mismatch_reason is not None:
                self._write_skipped_event(event, mismatch_reason)
            elif not self._post_event_with_retries(event):
                return
            with self._archive_lock:
                self._write_checkpoint(index + 1)

    def _resource_mismatch_reason(self, event: dict[str, object]) -> str | None:
        mismatches = []
        if event.get("lecture_id") != self.lecture_id:
            mismatches.append(
                f"lecture_id={event.get('lecture_id')!r}, configured "
                f"lecture_id={self.lecture_id!r}"
            )
        if event.get("classroom_id") != self.classroom_id:
            mismatches.append(
                f"classroom_id={event.get('classroom_id')!r}, configured "
                f"classroom_id={self.classroom_id!r}"
            )
        if not mismatches:
            return None
        return "lecture/classroom mismatch (" + "; ".join(mismatches) + ")"

    def _write_skipped_event(
        self, event: dict[str, object], reason: str
    ) -> None:
        skipped_path = self.output_path.with_name(
            f"{self.output_path.stem}.skipped.jsonl"
        )
        record = {"reason": reason, "event": event}
        with self._archive_lock:
            skipped_path.parent.mkdir(parents=True, exist_ok=True)
            with skipped_path.open("a", encoding="utf-8") as skipped_file:
                skipped_file.write(json.dumps(record) + "\n")
                skipped_file.flush()
                os.fsync(skipped_file.fileno())

    def _post_event_with_retries(self, event: dict[str, object]) -> bool:
        endpoint = f"{self.api_base_url}/events"
        headers = {"X-Camera-Key": self.camera_key}

        for attempt in range(self.retry_attempts):
            try:
                response = httpx.post(
                    endpoint,
                    json=event,
                    headers=headers,
                    timeout=DELIVERY_TIMEOUT_SECONDS,
                )
            except httpx.RequestError:
                if attempt + 1 == self.retry_attempts:
                    print(
                        "Backend is unreachable; event remains pending in "
                        f"{self.output_path}."
                    )
                    return False
                time.sleep(DELIVERY_BACKOFF_SECONDS * (2**attempt))
                continue

            if response.status_code in {200, 201, 202}:
                return True
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 == self.retry_attempts:
                    print(
                        f"Backend returned HTTP {response.status_code}; event "
                        f"remains pending in {self.output_path}."
                    )
                    return False
                delay = self._retry_after_seconds(response)
                time.sleep(
                    delay
                    if delay is not None
                    else DELIVERY_BACKOFF_SECONDS * (2**attempt)
                )
                continue

            if response.status_code == 422:
                if self._is_outside_lecture_window(response):
                    self._write_skipped_event(event, "outside lecture window")
                    return True
                fields = self._validation_detail_fields(response)
                fields_text = ", ".join(fields) if fields else "unknown"
                print(
                    f"Backend rejected an event with HTTP 422; validation detail "
                    f"fields: {fields_text}; event remains pending in "
                    f"{self.output_path}."
                )
                self._delivery_blocked = True
                return False

            print(
                f"Backend rejected an event with HTTP {response.status_code}; "
                f"event remains pending in {self.output_path}."
            )
            self._delivery_blocked = True
            return False

        return False

    @staticmethod
    def _is_outside_lecture_window(response: httpx.Response) -> bool:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            return False
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("code") == (
                "TIMESTAMP_OUTSIDE_ALLOWED_WINDOW"
            ):
                return True
        return False

    @staticmethod
    def _validation_detail_fields(response: httpx.Response) -> list[str]:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            return []

        details = payload.get("detail", []) if isinstance(payload, dict) else []
        fields: list[str] = []
        if isinstance(details, list):
            for item in details:
                if not isinstance(item, dict):
                    continue
                location = item.get("loc", [])
                if isinstance(location, list):
                    for value in location:
                        if isinstance(value, str) and value not in fields:
                            fields.append(value)
        return fields

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            seconds = float(value)
        except ValueError:
            return None
        return min(max(seconds, 0.0), MAX_RETRY_AFTER_SECONDS)

    @staticmethod
    def _read_resource_id(name: str, fallback: str) -> int | str:
        value = os.getenv(name)
        if value is None or not value.strip():
            return fallback
        try:
            resource_id = int(value)
        except ValueError:
            return fallback
        return resource_id if resource_id > 0 else fallback

    @staticmethod
    def _read_positive_int(name: str, fallback: int) -> int:
        value = os.getenv(name)
        if value is None:
            return fallback
        try:
            result = int(value)
        except ValueError:
            return fallback
        return result if result > 0 else fallback
