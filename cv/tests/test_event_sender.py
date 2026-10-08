import json
from datetime import datetime

import pytest

from cv.config import CLASSROOM_ID, LECTURE_ID
from cv.event_sender import EventSender


def test_send_appends_event_with_expected_schema_and_prints(
    tmp_path, capsys
) -> None:
    output_path = tmp_path / "data" / "events.jsonl"
    sender = EventSender(output_path)

    event = sender.send(track_id=12, event_type="ENTRY", confidence=0.87)

    saved_lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(saved_lines) == 1
    saved_event = json.loads(saved_lines[0])
    assert saved_event == event
    assert set(event) == {
        "student_id",
        "flagged_for_review",
        "classroom_id",
        "lecture_id",
        "event_type",
        "timestamp",
        "confidence",
        "source",
    }
    assert event["student_id"] == "UNKNOWN"
    assert event["flagged_for_review"] is True
    assert event["classroom_id"] == CLASSROOM_ID
    assert event["lecture_id"] == LECTURE_ID
    assert event["event_type"] == "ENTRY"
    assert event["confidence"] == 0.87
    assert event["source"] == "camera"
    assert datetime.fromisoformat(str(event["timestamp"])).utcoffset() is not None
    assert capsys.readouterr().out.strip() == (
        "ENTRY track_id=12 student_id=UNKNOWN (flagged for review)"
    )


def test_send_uses_mapped_student_id_without_review_flag(tmp_path) -> None:
    sender = EventSender(tmp_path / "events.jsonl")

    event = sender.send(
        track_id=12,
        event_type="ENTRY",
        confidence=0.87,
        student_id="STUDENT_A",
    )

    assert event["student_id"] == "STUDENT_A"
    assert event["flagged_for_review"] is False


def test_send_appends_each_event_as_a_separate_json_line(tmp_path) -> None:
    output_path = tmp_path / "events.jsonl"
    sender = EventSender(output_path)

    sender.send(track_id=1, event_type="ENTRY", confidence=0.8)
    sender.send(track_id=1, event_type="EXIT", confidence=0.9)

    saved_events = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event_type"] for event in saved_events] == ["ENTRY", "EXIT"]


@pytest.mark.parametrize("event_type", ["RETURN", "UNKNOWN", ""])
def test_send_rejects_event_types_outside_entry_exit(
    tmp_path, event_type: str
) -> None:
    sender = EventSender(tmp_path / "events.jsonl")

    with pytest.raises(ValueError, match="ENTRY or EXIT"):
        sender.send(track_id=1, event_type=event_type, confidence=0.9)  # type: ignore[arg-type]


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf")])
def test_send_rejects_invalid_confidence(
    tmp_path, confidence: float
) -> None:
    output_path = tmp_path / "events.jsonl"
    sender = EventSender(output_path)

    with pytest.raises(ValueError, match="confidence"):
        sender.send(track_id=1, event_type="ENTRY", confidence=confidence)

    assert not output_path.exists()
