import argparse
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from getpass import getpass
from pathlib import Path

import httpx

from app.config import Settings, get_settings

MIN_SIMULATED_STUDENTS = 4
UNKNOWN_STUDENT_ID = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SimulationSummary:
    accepted_count: int
    flagged_count: int
    duplicate_count: int
    jsonl_path: Path


def build_event_stream(
    classroom_id: int,
    lecture_id: int,
    lecture_start: datetime,
    duration_minutes: int,
    student_codes: list[str],
) -> list[dict[str, str | float | bool | int]]:
    if classroom_id < 1 or lecture_id < 1:
        raise ValueError("classroom_id and lecture_id must be positive.")
    if lecture_start.tzinfo is None or lecture_start.utcoffset() is None:
        raise ValueError("lecture_start must include a timezone offset.")
    if duration_minutes < 1:
        raise ValueError("duration_minutes must be positive.")
    normalized_codes = [code.strip() for code in student_codes]
    if len(normalized_codes) < MIN_SIMULATED_STUDENTS:
        raise ValueError(
            f"At least {MIN_SIMULATED_STUDENTS} enrolled student codes are required."
        )
    if any(not code or code.upper() == UNKNOWN_STUDENT_ID for code in normalized_codes):
        raise ValueError(
            "Provide non-empty enrolled codes; UNKNOWN is simulated separately."
        )
    if len({code.casefold() for code in normalized_codes}) != len(normalized_codes):
        raise ValueError("Student codes must be unique.")

    duration = timedelta(minutes=duration_minutes)
    event_rows: list[tuple[datetime, dict[str, str | float | bool | int]]] = []

    def add_event(
        student_code: str,
        event_type: str,
        progress: float,
        *,
        flagged_for_review: bool = False,
    ) -> None:
        event_time = lecture_start + duration * progress
        payload: dict[str, str | float | bool | int] = {
            "student_id": student_code,
            "classroom_id": classroom_id,
            "lecture_id": lecture_id,
            "event_type": event_type,
            "timestamp": event_time.isoformat(),
            "confidence": 0.95 if not flagged_for_review else 0.9,
            "source": "camera",
            "flagged_for_review": flagged_for_review,
            "presence_confirmed": True,
            "client_event_id": f"sim-{uuid.uuid4().hex}",
        }
        event_rows.append((event_time, payload))

    add_event(normalized_codes[0], "ENTRY", 0.05)
    add_event(normalized_codes[1], "ENTRY", 0.05)
    add_event(normalized_codes[1], "EXIT", 0.50)
    add_event(normalized_codes[2], "ENTRY", 0.05)
    add_event(normalized_codes[2], "EXIT", 0.25)
    add_event(normalized_codes[2], "ENTRY", 0.50)
    add_event(normalized_codes[2], "EXIT", 0.75)
    for student_code in normalized_codes[4:]:
        add_event(student_code, "ENTRY", 0.05)
    add_event(
        UNKNOWN_STUDENT_ID,
        "ENTRY",
        0.15,
        flagged_for_review=True,
    )

    event_rows.sort(
        key=lambda row: (
            row[0],
            str(row[1]["student_id"]),
            str(row[1]["event_type"]),
        )
    )
    return [payload for _, payload in event_rows]


def append_jsonl(
    output_path: Path, events: list[dict[str, str | float | bool | int]]
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as event_file:
        for event in events:
            event_file.write(json.dumps(event, separators=(",", ":")) + "\n")


def submit_event_batch(
    client: httpx.Client,
    base_url: str,
    camera_key: str,
    events: list[dict[str, str | float | bool | int]],
    settings: Settings,
    jsonl_path: Path,
) -> SimulationSummary:
    endpoint = f"{base_url.rstrip('/')}/events/batch"
    headers = {"X-Camera-Key": camera_key}

    for attempt in range(settings.simulator_retry_attempts + 1):
        try:
            response = client.post(endpoint, json=events, headers=headers)
        except httpx.RequestError as exc:
            if attempt >= settings.simulator_retry_attempts:
                raise RuntimeError(
                    f"Could not reach the API after retries. Events remain in "
                    f"{jsonl_path}."
                ) from exc
            time.sleep(settings.simulator_retry_backoff_seconds * (2**attempt))
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if attempt >= settings.simulator_retry_attempts:
                raise RuntimeError(
                    f"API returned HTTP {response.status_code} after retries. "
                    f"Events remain in {jsonl_path}."
                )
            delay = _retry_after_seconds(response)
            if delay is None:
                delay = settings.simulator_retry_backoff_seconds * (2**attempt)
            time.sleep(delay)
            continue

        if response.status_code not in {200, 201, 202}:
            raise RuntimeError(
                f"API rejected the event batch with HTTP {response.status_code}. "
                f"Events remain in {jsonl_path}; review the API error before retrying."
            )

        try:
            result = response.json()
            summary = SimulationSummary(
                accepted_count=int(result["accepted_count"]),
                flagged_count=int(result["flagged_count"]),
                duplicate_count=int(result["duplicate_count"]),
                jsonl_path=jsonl_path,
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError(
                f"API response did not match the event batch contract. "
                f"Events remain in {jsonl_path}."
            ) from exc

        if (
            summary.accepted_count + summary.flagged_count + summary.duplicate_count
            != len(events)
        ):
            raise RuntimeError(
                f"API response counts do not match the submitted batch. "
                f"Events remain in {jsonl_path}."
            )
        return summary

    raise RuntimeError(f"Events remain in {jsonl_path}; delivery did not complete.")


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def parse_student_codes(value: str) -> list[str]:
    codes = [item.strip() for item in value.split(",")]
    if any(not code for code in codes):
        raise argparse.ArgumentTypeError(
            "Student codes must be comma-separated values."
        )
    if len(codes) < MIN_SIMULATED_STUDENTS:
        raise argparse.ArgumentTypeError(
            f"Provide at least {MIN_SIMULATED_STUDENTS} enrolled student codes."
        )
    if len({code.casefold() for code in codes}) != len(codes):
        raise argparse.ArgumentTypeError("Student codes must be unique.")
    if any(code.upper() == UNKNOWN_STUDENT_ID for code in codes):
        raise argparse.ArgumentTypeError(
            "Do not include UNKNOWN; the simulator generates that review case."
        )
    return codes


def parse_lecture_start(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Lecture start must be an ISO 8601 datetime."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            "Lecture start must include a timezone offset, for example +05:30 or Z."
        )
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a realistic ENTRY/EXIT demo stream to the events API."
    )
    parser.add_argument(
        "--base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    )
    parser.add_argument("--classroom-id", type=int, required=True)
    parser.add_argument("--lecture-id", type=int, required=True)
    parser.add_argument("--lecture-start", type=parse_lecture_start, required=True)
    parser.add_argument("--duration-minutes", type=int, default=60)
    parser.add_argument("--student-codes", type=parse_student_codes, required=True)
    parser.add_argument(
        "--jsonl-output",
        type=Path,
        default=Path("data") / "simulated_events.jsonl",
    )
    arguments = parser.parse_args()

    camera_key = os.getenv("ECOSENSE_CAMERA_KEY") or getpass("Camera API key: ")
    if not camera_key.strip():
        parser.error("A camera API key is required.")
    settings = get_settings()

    try:
        events = build_event_stream(
            arguments.classroom_id,
            arguments.lecture_id,
            arguments.lecture_start,
            arguments.duration_minutes,
            arguments.student_codes,
        )
        if len(events) > settings.max_event_batch_size:
            raise ValueError(
                f"Generated stream has {len(events)} events, exceeding the "
                f"configured batch limit of {settings.max_event_batch_size}."
            )
        append_jsonl(arguments.jsonl_output, events)
        with httpx.Client(timeout=settings.simulator_request_timeout_seconds) as client:
            summary = submit_event_batch(
                client,
                arguments.base_url,
                camera_key,
                events,
                settings,
                arguments.jsonl_output,
            )
    except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    print(
        "Simulation delivery complete: "
        f"accepted={summary.accepted_count}, flagged={summary.flagged_count}, "
        f"duplicates={summary.duplicate_count}, jsonl={summary.jsonl_path}"
    )


if __name__ == "__main__":
    main()
