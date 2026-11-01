import json
import threading
import time
from datetime import datetime

import httpx
import pytest
from cv.config import CLASSROOM_ID, LECTURE_ID
from cv.event_sender import EventSender


@pytest.fixture(autouse=True)
def disable_backend_delivery(monkeypatch) -> None:
    monkeypatch.setattr("cv.event_sender.load_dotenv", lambda *_args, **_kwargs: False)
    for name in (
        "API_BASE_URL",
        "ECOSENSE_CAMERA_KEY",
        "CLASSROOM_ID",
        "LECTURE_ID",
        "CV_DELIVERY_RETRY_ATTEMPTS",
    ):
        monkeypatch.delenv(name, raising=False)


def configured_sender(monkeypatch, output_path):
    monkeypatch.setenv("API_BASE_URL", "http://backend.test")
    monkeypatch.setenv("ECOSENSE_CAMERA_KEY", "test-camera-key")
    monkeypatch.setenv("CLASSROOM_ID", "1")
    monkeypatch.setenv("LECTURE_ID", "12")
    return EventSender(output_path)


def wait_for_checkpoint(checkpoint_path, expected: int) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if checkpoint_path.exists():
            try:
                if int(checkpoint_path.read_text(encoding="ascii")) == expected:
                    return
            except (OSError, ValueError):
                pass
        threading.Event().wait(0.01)
    raise AssertionError(f"delivery checkpoint did not reach {expected}")


def test_send_appends_event_with_expected_schema_and_prints(tmp_path, capsys) -> None:
    output_path = tmp_path / "data" / "events.jsonl"
    sender = EventSender(output_path)

    event = sender.send(track_id=12, event_type="ENTRY", confidence=0.87)

    saved_lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(saved_lines) == 1
    saved_event = json.loads(saved_lines[0])
    assert saved_event == event
    assert set(event) == {
        "client_event_id",
        "student_id",
        "flagged_for_review",
        "classroom_id",
        "lecture_id",
        "event_type",
        "timestamp",
        "confidence",
        "source",
        "presence_confirmed",
    }
    assert event["student_id"] == "UNKNOWN"
    assert event["flagged_for_review"] is True
    assert event["classroom_id"] == CLASSROOM_ID
    assert event["lecture_id"] == LECTURE_ID
    assert event["event_type"] == "ENTRY"
    assert event["confidence"] == 0.87
    assert event["source"] == "camera"
    assert event["presence_confirmed"] is True
    assert datetime.fromisoformat(str(event["timestamp"])).utcoffset() is not None
    output = capsys.readouterr().out
    assert "ENTRY track_id=12 student_id=UNKNOWN (flagged for review)" in output
    assert "event remains in" in output.lower()


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


@pytest.mark.parametrize("accepted_status", [200, 201, 202])
def test_send_posts_only_after_event_is_durable_in_jsonl(
    tmp_path, monkeypatch, accepted_status: int
) -> None:
    output_path = tmp_path / "events.jsonl"
    sender = configured_sender(monkeypatch, output_path)
    posted: list[dict[str, object]] = []
    posted_before_archive: list[bool] = []

    def post(url, *, json, headers, timeout):
        posted_before_archive.append(
            output_path.exists() and output_path.stat().st_size > 0
        )
        posted.append(json)
        assert url == "http://backend.test/events"
        assert headers == {"X-Camera-Key": "test-camera-key"}
        assert timeout > 0
        return httpx.Response(accepted_status)

    monkeypatch.setattr("cv.event_sender.httpx.post", post)
    try:
        event = sender.send(
            track_id=12,
            event_type="ENTRY",
            confidence=0.87,
            student_id="STUDENT_A",
        )
        wait_for_checkpoint(sender.checkpoint_path, 1)
    finally:
        sender.close()

    assert posted_before_archive == [True]
    assert posted == [event]
    assert event["client_event_id"]
    assert event["classroom_id"] == 1
    assert event["lecture_id"] == 12


def test_send_retries_rate_limit_then_accepts_event(tmp_path, monkeypatch) -> None:
    sender = configured_sender(monkeypatch, tmp_path / "events.jsonl")
    statuses = iter((429, 201))
    event_ids: list[object] = []
    monkeypatch.setattr("cv.event_sender.time.sleep", lambda _seconds: None)

    def post(*_args, json, **_kwargs):
        event_ids.append(json["client_event_id"])
        return httpx.Response(
            next(statuses),
            headers={"Retry-After": "0"},
        )

    monkeypatch.setattr(
        "cv.event_sender.httpx.post",
        post,
    )
    try:
        sender.send(track_id=1, event_type="ENTRY", confidence=0.9)
        wait_for_checkpoint(sender.checkpoint_path, 1)
    finally:
        sender.close()

    assert len(event_ids) == 2
    assert len(set(event_ids)) == 1


def test_offline_backend_keeps_event_pending_for_later_retry(
    tmp_path, monkeypatch, capsys
) -> None:
    output_path = tmp_path / "events.jsonl"
    monkeypatch.setenv("CV_DELIVERY_RETRY_ATTEMPTS", "2")
    sender = configured_sender(monkeypatch, output_path)
    attempts = 0

    def post(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise httpx.ConnectError("offline")
        return httpx.Response(201)

    monkeypatch.setattr("cv.event_sender.httpx.post", post)
    monkeypatch.setattr("cv.event_sender.time.sleep", lambda _seconds: None)
    try:
        sender.send(track_id=1, event_type="ENTRY", confidence=0.9)
        deadline = time.monotonic() + 3
        while attempts < 2 and time.monotonic() < deadline:
            threading.Event().wait(0.01)
        assert attempts == 2
        assert sender.checkpoint_path.read_text(encoding="ascii").strip() == "0"
        assert len(output_path.read_text(encoding="utf-8").splitlines()) == 1

        sender._delivery_wake.set()
        wait_for_checkpoint(sender.checkpoint_path, 1)
    finally:
        sender.close()

    assert attempts == 3
    assert "event remains pending" in capsys.readouterr().out


def test_permanent_client_error_keeps_event_pending_without_retry(
    tmp_path, monkeypatch, capsys
) -> None:
    sender = configured_sender(monkeypatch, tmp_path / "events.jsonl")
    attempts = 0

    def post(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        return httpx.Response(422)

    monkeypatch.setattr("cv.event_sender.httpx.post", post)
    try:
        sender.send(track_id=1, event_type="ENTRY", confidence=0.9)
        deadline = time.monotonic() + 3
        while attempts == 0 and time.monotonic() < deadline:
            threading.Event().wait(0.01)
        assert attempts == 1
        assert sender.checkpoint_path.read_text(encoding="ascii").strip() == "0"
    finally:
        sender.close()

    assert "HTTP 422" in capsys.readouterr().out


def test_mismatched_resources_are_moved_to_skipped_archive(
    tmp_path, monkeypatch, capsys
) -> None:
    output_path = tmp_path / "events.jsonl"
    mismatched_event = {
        "client_event_id": "old-event",
        "student_id": "STUDENT_A",
        "flagged_for_review": False,
        "classroom_id": 8,
        "lecture_id": 7,
        "event_type": "ENTRY",
        "timestamp": "2030-01-01T10:00:00+00:00",
        "confidence": 0.9,
        "source": "camera",
        "presence_confirmed": True,
    }
    output_path.write_text(json.dumps(mismatched_event) + "\n", encoding="utf-8")
    output_path.with_suffix(".delivery").write_text("0\n", encoding="ascii")

    posted = []
    sender = configured_sender(monkeypatch, output_path)
    monkeypatch.setattr(
        "cv.event_sender.httpx.post",
        lambda *_args, **_kwargs: posted.append(True) or httpx.Response(200),
    )
    try:
        wait_for_checkpoint(output_path.with_suffix(".delivery"), 1)
    finally:
        sender.close()

    skipped_path = tmp_path / "events.skipped.jsonl"
    skipped = json.loads(skipped_path.read_text(encoding="utf-8"))
    assert skipped["event"] == mismatched_event
    assert "lecture/classroom mismatch" in skipped["reason"]
    assert posted == []
    assert "2030-01-01T10:00:00+00:00" in json.dumps(skipped["event"])


def test_outside_window_422_moves_event_to_skipped_archive(
    tmp_path, monkeypatch
) -> None:
    output_path = tmp_path / "events.jsonl"
    sender = configured_sender(monkeypatch, output_path)
    response = httpx.Response(
        422,
        json={
            "error": {
                "code": "TIMESTAMP_OUTSIDE_ALLOWED_WINDOW",
                "message": "Event timestamp is outside the allowed lecture time window.",
            }
        },
    )
    monkeypatch.setattr(
        "cv.event_sender.httpx.post",
        lambda *_args, **_kwargs: response,
    )
    try:
        sender.send(track_id=1, event_type="ENTRY", confidence=0.9)
        wait_for_checkpoint(sender.checkpoint_path, 1)
    finally:
        sender.close()

    skipped = json.loads((tmp_path / "events.skipped.jsonl").read_text(encoding="utf-8"))
    assert skipped["reason"] == "outside lecture window"


def test_checkpoint_ahead_names_files_and_safe_fix(tmp_path, monkeypatch, capsys) -> None:
    output_path = tmp_path / "events.jsonl"
    output_path.write_text("{}\n", encoding="utf-8")
    checkpoint_path = output_path.with_suffix(".delivery")
    checkpoint_path.write_text("3\n", encoding="ascii")
    sender = configured_sender(monkeypatch, output_path)
    try:
        sender._drain_archive()
    finally:
        sender.close()

    output = capsys.readouterr().out
    assert str(checkpoint_path) in output or "events.delivery" in output
    assert str(output_path) in output
    assert "Safe fix" in output


def test_422_validation_detail_prints_field_names_only(
    tmp_path, monkeypatch, capsys
) -> None:
    output_path = tmp_path / "events.jsonl"
    sender = configured_sender(monkeypatch, output_path)
    response = httpx.Response(
        422,
        json={
            "detail": [
                {
                    "loc": ["body", "timestamp"],
                    "msg": "timestamp is invalid",
                    "type": "value_error",
                },
                {
                    "loc": ["body", "student_id"],
                    "msg": "student is invalid",
                    "type": "value_error",
                },
            ]
        },
    )
    monkeypatch.setattr(
        "cv.event_sender.httpx.post",
        lambda *_args, **_kwargs: response,
    )
    try:
        sender.send(track_id=1, event_type="ENTRY", confidence=0.9)
        deadline = time.monotonic() + 3
        output = ""
        while time.monotonic() < deadline:
            output += capsys.readouterr().out
            if "HTTP 422" in output:
                break
            threading.Event().wait(0.01)
    finally:
        sender.close()

    output += capsys.readouterr().out
    assert "timestamp, student_id" in output
    assert "timestamp is invalid" not in output
    assert "test-camera-key" not in output


def test_sender_resumes_pending_jsonl_after_restart(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "events.jsonl"
    archived_event = {
        "client_event_id": "stable-id",
        "student_id": "STUDENT_A",
        "flagged_for_review": False,
        "classroom_id": 1,
        "lecture_id": 12,
        "event_type": "ENTRY",
        "timestamp": "2030-01-01T10:00:00+00:00",
        "confidence": 0.9,
        "source": "camera",
        "presence_confirmed": True,
    }
    output_path.write_text(json.dumps(archived_event) + "\n", encoding="utf-8")
    checkpoint_path = output_path.with_suffix(".delivery")
    checkpoint_path.write_text("0\n", encoding="ascii")
    sender = configured_sender(monkeypatch, output_path)
    posted: list[dict[str, object]] = []
    monkeypatch.setattr(
        "cv.event_sender.httpx.post",
        lambda *_args, json, **_kwargs: posted.append(json) or httpx.Response(200),
    )
    try:
        wait_for_checkpoint(checkpoint_path, 1)
    finally:
        sender.close()

    assert posted == [archived_event]


@pytest.mark.parametrize("event_type", ["RETURN", "UNKNOWN", ""])
def test_send_rejects_event_types_outside_entry_exit(tmp_path, event_type: str) -> None:
    sender = EventSender(tmp_path / "events.jsonl")

    with pytest.raises(ValueError, match="ENTRY or EXIT"):
        sender.send(track_id=1, event_type=event_type, confidence=0.9)  # type: ignore[arg-type]


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf")])
def test_send_rejects_invalid_confidence(tmp_path, confidence: float) -> None:
    output_path = tmp_path / "events.jsonl"
    sender = EventSender(output_path)

    with pytest.raises(ValueError, match="confidence"):
        sender.send(track_id=1, event_type="ENTRY", confidence=confidence)

    assert not output_path.exists()
