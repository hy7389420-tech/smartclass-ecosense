from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

PresenceStatus = Literal["ABSENT", "INSIDE", "OUTSIDE", "PARTIAL"]


@dataclass(frozen=True, slots=True)
class PresenceEvent:
    event_type: str
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class EventIssue:
    event_index: int
    reason: str


@dataclass(frozen=True, slots=True)
class PresenceResult:
    inside_minutes: float
    outside_minutes: float
    exit_count: int
    return_count: int
    first_entry: datetime | None
    last_exit: datetime | None
    status: PresenceStatus
    issues: tuple[EventIssue, ...]


@dataclass(frozen=True, slots=True)
class DerivedEventSequence:
    events: tuple[PresenceEvent, ...]
    issues: tuple[EventIssue, ...]


def _as_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return value.astimezone(UTC)


def calculate_presence(
    events: Sequence[PresenceEvent],
    lecture_start: datetime,
    lecture_end: datetime,
    now: datetime | None = None,
) -> PresenceResult:
    start = _as_utc(lecture_start, "lecture_start")
    end = _as_utc(lecture_end, "lecture_end")
    if end <= start:
        raise ValueError("lecture_end must be after lecture_start.")

    current_time = end if now is None else _as_utc(now, "now")
    calculation_end = min(max(current_time, start), end)
    issues: list[EventIssue] = []
    indexed_events = [
        (index, event, _as_utc(event.timestamp, "event timestamp"))
        for index, event in enumerate(events)
    ]
    indexed_events.sort(key=lambda item: item[2])

    seen_event_keys: set[tuple[str, datetime]] = set()
    valid_events: list[tuple[int, str, datetime]] = []
    for index, event, timestamp in indexed_events:
        event_type = event.event_type.strip().upper()
        if timestamp < start or timestamp > end:
            issues.append(EventIssue(index, "outside_lecture_window"))
            continue
        if timestamp > calculation_end:
            issues.append(EventIssue(index, "after_calculation_time"))
            continue
        if event_type not in {"ENTRY", "EXIT", "RETURN"}:
            issues.append(EventIssue(index, "unsupported_event_type"))
            continue

        event_key = event_type, timestamp
        if event_key in seen_event_keys:
            issues.append(EventIssue(index, "duplicate_event"))
            continue
        seen_event_keys.add(event_key)
        valid_events.append((index, event_type, timestamp))

    first_entry: datetime | None = None
    last_exit: datetime | None = None
    inside = False
    outside_start: datetime | None = None
    outside_seconds = 0.0
    exit_count = 0
    return_count = 0

    for index, event_type, timestamp in valid_events:
        if event_type == "ENTRY":
            if first_entry is None:
                first_entry = timestamp
                inside = True
            elif inside:
                issues.append(EventIssue(index, "entry_while_inside"))
            else:
                issues.append(EventIssue(index, "entry_after_exit_requires_return"))
        elif event_type == "EXIT":
            if first_entry is None:
                issues.append(EventIssue(index, "exit_before_entry"))
            elif not inside:
                issues.append(EventIssue(index, "exit_while_outside"))
            else:
                inside = False
                outside_start = timestamp
                last_exit = timestamp
                exit_count += 1
        elif event_type == "RETURN":
            if first_entry is None:
                issues.append(EventIssue(index, "return_before_entry"))
            elif inside:
                issues.append(EventIssue(index, "return_while_inside"))
            else:
                outside_seconds += (timestamp - outside_start).total_seconds()
                outside_start = None
                inside = True
                return_count += 1

    if first_entry is None:
        inside_minutes = 0.0
        outside_minutes = 0.0
        result_status: PresenceStatus = "ABSENT"
    else:
        if outside_start is not None:
            outside_seconds += max(
                0.0, (calculation_end - outside_start).total_seconds()
            )
        elapsed_seconds = max(0.0, (calculation_end - first_entry).total_seconds())
        inside_minutes = round(max(0.0, elapsed_seconds - outside_seconds) / 60, 2)
        outside_minutes = round(outside_seconds / 60, 2)

        if calculation_end < end:
            result_status = "INSIDE" if inside else "OUTSIDE"
        elif (
            first_entry == start
            and inside
            and exit_count == 0
            and inside_minutes == (end - start).total_seconds() / 60
        ):
            result_status = "INSIDE"
        else:
            result_status = "PARTIAL"

    return PresenceResult(
        inside_minutes=inside_minutes,
        outside_minutes=outside_minutes,
        exit_count=exit_count,
        return_count=return_count,
        first_entry=first_entry,
        last_exit=last_exit,
        status=result_status,
        issues=tuple(issues),
    )


def derive_event_types(raw_events: Sequence[PresenceEvent]) -> DerivedEventSequence:
    indexed_events = [
        (index, event, _as_utc(event.timestamp, "event timestamp"))
        for index, event in enumerate(raw_events)
    ]
    indexed_events.sort(key=lambda item: item[2])

    derived: list[PresenceEvent] = []
    issues: list[EventIssue] = []
    seen_event_keys: set[tuple[str, datetime]] = set()
    has_entered = False
    inside = False

    for index, event, timestamp in indexed_events:
        raw_type = event.event_type.strip().upper()
        if raw_type not in {"ENTRY", "EXIT"}:
            issues.append(EventIssue(index, "unsupported_raw_event_type"))
            continue

        event_key = raw_type, timestamp
        if event_key in seen_event_keys:
            issues.append(EventIssue(index, "duplicate_event"))
            continue
        seen_event_keys.add(event_key)

        if raw_type == "ENTRY":
            if inside:
                issues.append(EventIssue(index, "entry_while_inside"))
                continue
            event_type = "RETURN" if has_entered else "ENTRY"
            has_entered = True
            inside = True
        else:
            if not inside:
                reason = "exit_while_outside" if has_entered else "exit_before_entry"
                issues.append(EventIssue(index, reason))
                continue
            event_type = "EXIT"
            inside = False

        derived.append(PresenceEvent(event_type=event_type, timestamp=timestamp))

    return DerivedEventSequence(events=tuple(derived), issues=tuple(issues))
