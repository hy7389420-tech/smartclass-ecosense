import argparse
import json
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.database import session_scope
from app.schemas.events import EventIngestRequest
from app.services.camera_auth import authenticate_camera_key
from app.services.events import ingest_event


@dataclass(frozen=True)
class ImportSummary:
    accepted_count: int
    flagged_count: int
    duplicate_count: int


def import_events_jsonl(
    file_path: Path,
    session: Session,
    camera_key: str | None,
) -> ImportSummary:
    camera = authenticate_camera_key(session, camera_key)
    accepted_count = 0
    flagged_count = 0
    duplicate_count = 0

    with file_path.open(encoding="utf-8") as event_file:
        for line_number, line in enumerate(event_file, start=1):
            if not line.strip():
                continue
            try:
                payload_data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}.") from exc
            try:
                payload = EventIngestRequest.model_validate(payload_data)
            except ValidationError as exc:
                raise ValueError(
                    f"Invalid event payload on line {line_number}."
                ) from exc

            result = ingest_event(session, payload, camera)
            if result.duplicate:
                duplicate_count += 1
            elif result.flagged_for_review:
                flagged_count += 1
            else:
                accepted_count += 1

    return ImportSummary(
        accepted_count=accepted_count,
        flagged_count=flagged_count,
        duplicate_count=duplicate_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import CV event JSONL records using the event ingestion service."
    )
    parser.add_argument("file", type=Path)
    arguments = parser.parse_args()
    if not arguments.file.is_file():
        parser.error("The JSONL input file does not exist.")

    camera_key = (
        getpass("Camera API key: ") if get_settings().require_camera_key else None
    )
    try:
        with session_scope() as session:
            summary = import_events_jsonl(arguments.file, session, camera_key)
    except (ApiError, ValueError) as exc:
        message = exc.message if isinstance(exc, ApiError) else str(exc)
        parser.error(message)

    print(
        "Import complete: "
        f"accepted={summary.accepted_count}, flagged={summary.flagged_count}, "
        f"duplicates={summary.duplicate_count}"
    )


if __name__ == "__main__":
    main()
