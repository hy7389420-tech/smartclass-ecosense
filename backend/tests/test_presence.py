from datetime import UTC, datetime

import pytest

from app.services.presence import (
    PresenceEvent,
    calculate_presence,
    derive_event_types,
)

LECTURE_START = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)
LECTURE_END = datetime(2026, 10, 25, 11, 0, tzinfo=UTC)


def at(hour: int, minute: int) -> datetime:
    return datetime(2026, 10, 25, hour, minute, tzinfo=UTC)


def event(event_type: str, hour: int, minute: int) -> PresenceEvent:
    return PresenceEvent(event_type, at(hour, minute))


def test_example_counts_only_actual_time_after_entry():
    result = calculate_presence(
        [
            event("ENTRY", 10, 2),
            event("EXIT", 10, 30),
            event("RETURN", 10, 42),
        ],
        LECTURE_START,
        LECTURE_END,
    )

    assert result.inside_minutes == 46
    assert result.outside_minutes == 12
    assert result.exit_count == 1
    assert result.return_count == 1
    assert result.first_entry == at(10, 2)
    assert result.last_exit == at(10, 30)
    assert result.status == "PARTIAL"
    assert result.issues == ()


def test_student_who_never_exits():
    result = calculate_presence(
        [event("ENTRY", 10, 2)],
        LECTURE_START,
        LECTURE_END,
    )

    assert result.inside_minutes == 58
    assert result.outside_minutes == 0
    assert result.exit_count == 0
    assert result.return_count == 0
    assert result.status == "PARTIAL"


def test_exit_without_return_counts_outside_until_lecture_end():
    result = calculate_presence(
        [event("ENTRY", 10, 2), event("EXIT", 10, 30)],
        LECTURE_START,
        LECTURE_END,
    )

    assert result.inside_minutes == 28
    assert result.outside_minutes == 30
    assert result.exit_count == 1
    assert result.return_count == 0
    assert result.status == "PARTIAL"


def test_multiple_exit_and_return_cycles():
    result = calculate_presence(
        [
            event("ENTRY", 10, 0),
            event("EXIT", 10, 10),
            event("RETURN", 10, 15),
            event("EXIT", 10, 30),
            event("RETURN", 10, 40),
        ],
        LECTURE_START,
        LECTURE_END,
    )

    assert result.inside_minutes == 45
    assert result.outside_minutes == 15
    assert result.exit_count == 2
    assert result.return_count == 2


def test_student_with_no_entry_is_absent():
    result = calculate_presence([], LECTURE_START, LECTURE_END)

    assert result.inside_minutes == 0
    assert result.outside_minutes == 0
    assert result.exit_count == 0
    assert result.return_count == 0
    assert result.first_entry is None
    assert result.last_exit is None
    assert result.status == "ABSENT"


def test_out_of_window_events_are_ignored_and_flagged():
    result = calculate_presence(
        [
            event("ENTRY", 9, 59),
            event("ENTRY", 10, 5),
            event("EXIT", 11, 1),
        ],
        LECTURE_START,
        LECTURE_END,
    )

    assert result.inside_minutes == 55
    assert [issue.event_index for issue in result.issues] == [0, 2]
    assert [issue.reason for issue in result.issues] == [
        "outside_lecture_window",
        "outside_lecture_window",
    ]


def test_duplicate_events_are_ignored_and_flagged():
    result = calculate_presence(
        [
            event("ENTRY", 10, 0),
            event("ENTRY", 10, 0),
        ],
        LECTURE_START,
        LECTURE_END,
    )

    assert result.inside_minutes == 60
    assert [(issue.event_index, issue.reason) for issue in result.issues] == [
        (1, "duplicate_event")
    ]


def test_unsorted_events_are_processed_in_timestamp_order():
    result = calculate_presence(
        [
            event("RETURN", 10, 42),
            event("EXIT", 10, 30),
            event("ENTRY", 10, 2),
        ],
        LECTURE_START,
        LECTURE_END,
    )

    assert result.inside_minutes == 46
    assert result.outside_minutes == 12
    assert result.issues == ()


def test_ongoing_lecture_uses_now_to_close_open_presence_intervals():
    result = calculate_presence(
        [
            event("ENTRY", 10, 2),
            event("EXIT", 10, 30),
            event("RETURN", 10, 42),
        ],
        LECTURE_START,
        LECTURE_END,
        now=at(10, 50),
    )

    assert result.inside_minutes == 36
    assert result.outside_minutes == 12
    assert result.status == "INSIDE"


def test_ongoing_lecture_with_open_exit_is_outside_until_now():
    result = calculate_presence(
        [event("ENTRY", 10, 2), event("EXIT", 10, 30)],
        LECTURE_START,
        LECTURE_END,
        now=at(10, 50),
    )

    assert result.inside_minutes == 28
    assert result.outside_minutes == 20
    assert result.status == "OUTSIDE"


def test_invalid_event_sequence_is_flagged_and_not_counted():
    result = calculate_presence(
        [
            event("EXIT", 10, 1),
            event("ENTRY", 10, 2),
            event("EXIT", 10, 3),
            event("EXIT", 10, 4),
        ],
        LECTURE_START,
        LECTURE_END,
    )

    assert result.inside_minutes == 1
    assert result.outside_minutes == 57
    assert [(issue.event_index, issue.reason) for issue in result.issues] == [
        (0, "exit_before_entry"),
        (3, "exit_while_outside"),
    ]


def test_naive_timestamps_and_invalid_lecture_windows_are_rejected():
    with pytest.raises(ValueError, match="lecture_start must include a timezone"):
        calculate_presence([], LECTURE_START.replace(tzinfo=None), LECTURE_END)

    with pytest.raises(ValueError, match="lecture_end must be after"):
        calculate_presence([], LECTURE_END, LECTURE_START)


def test_camera_entry_exit_stream_derives_return_after_exit():
    result = derive_event_types(
        [
            event("ENTRY", 10, 2),
            event("EXIT", 10, 30),
            event("ENTRY", 10, 42),
            event("EXIT", 10, 50),
        ]
    )

    assert [item.event_type for item in result.events] == [
        "ENTRY",
        "EXIT",
        "RETURN",
        "EXIT",
    ]
    assert result.issues == ()


def test_camera_sequence_problems_are_reported():
    result = derive_event_types(
        [
            event("EXIT", 10, 0),
            event("ENTRY", 10, 2),
            event("ENTRY", 10, 3),
        ]
    )

    assert [item.event_type for item in result.events] == ["ENTRY"]
    assert [(issue.event_index, issue.reason) for issue in result.issues] == [
        (0, "exit_before_entry"),
        (2, "entry_while_inside"),
    ]
