import pytest

from cv.line_counter import LineCounter

LINE_START = (0.5, 0.0)
LINE_END = (0.5, 1.0)


def test_first_point_only_sets_initial_side() -> None:
    counter = LineCounter(LINE_START, LINE_END, cooldown_seconds=2.0)

    assert counter.update(1, (0.25, 0.5), 0.0) is None
    assert counter.update(1, (0.4, 0.5), 1.0) is None


def test_negative_to_positive_crossing_is_entry() -> None:
    counter = LineCounter(LINE_START, LINE_END, cooldown_seconds=2.0)
    counter.update(1, (0.75, 0.5), 0.0)

    event = counter.update(1, (0.25, 0.5), 2.0)

    assert event is not None
    assert (event.track_id, event.event_type) == (1, "ENTRY")


def test_positive_to_negative_crossing_is_exit() -> None:
    counter = LineCounter(LINE_START, LINE_END, cooldown_seconds=2.0)
    counter.update(1, (0.25, 0.5), 0.0)

    event = counter.update(1, (0.75, 0.5), 2.0)

    assert event is not None
    assert (event.track_id, event.event_type) == (1, "EXIT")


def test_crossing_during_cooldown_is_suppressed() -> None:
    counter = LineCounter(LINE_START, LINE_END, cooldown_seconds=2.0)
    counter.update(1, (0.75, 0.5), 0.0)
    assert counter.update(1, (0.25, 0.5), 2.0) is not None

    assert counter.update(1, (0.75, 0.5), 3.0) is None
    event = counter.update(1, (0.25, 0.5), 4.0)

    assert event is not None
    assert event.event_type == "ENTRY"


def test_jitter_near_line_does_not_repeat_crossing_after_cooldown() -> None:
    counter = LineCounter(LINE_START, LINE_END, cooldown_seconds=2.0)
    points = [
        (0.75, 0.5),
        (0.49, 0.5),
        (0.25, 0.5),
        (0.51, 0.5),
        (0.49, 0.5),
        (0.51, 0.5),
        (0.49, 0.5),
    ]

    events = [
        event
        for timestamp, point in enumerate(points, start=0)
        if (event := counter.update(14, point, timestamp * 3.0)) is not None
    ]

    assert [(event.track_id, event.event_type) for event in events] == [
        (14, "ENTRY")
    ]


def test_each_track_id_keeps_its_own_initial_side() -> None:
    counter = LineCounter(LINE_START, LINE_END, cooldown_seconds=2.0)
    counter.update(1, (0.75, 0.5), 0.0)
    counter.update(2, (0.25, 0.5), 0.0)

    event = counter.update(1, (0.25, 0.5), 2.0)

    assert event is not None
    assert (event.track_id, event.event_type) == (1, "ENTRY")
    assert counter.update(2, (0.25, 0.5), 2.0) is None


def test_point_on_line_does_not_create_crossing() -> None:
    counter = LineCounter(LINE_START, LINE_END, cooldown_seconds=2.0)
    counter.update(1, (0.75, 0.5), 0.0)

    assert counter.update(1, (0.5, 0.5), 1.0) is None
    event = counter.update(1, (0.25, 0.5), 2.0)

    assert event is not None
    assert event.event_type == "ENTRY"


def test_line_endpoints_must_be_different() -> None:
    with pytest.raises(ValueError, match="different"):
        LineCounter((0.5, 0.5), (0.5, 0.5), cooldown_seconds=2.0)


@pytest.mark.parametrize("cooldown", [-1.0, float("inf"), float("nan")])
def test_cooldown_must_be_finite_and_non_negative(cooldown: float) -> None:
    with pytest.raises(ValueError, match="Cooldown"):
        LineCounter(LINE_START, LINE_END, cooldown_seconds=cooldown)


@pytest.mark.parametrize(
    "hysteresis_distance",
    [-1.0, float("inf"), float("nan")],
)
def test_hysteresis_distance_must_be_finite_and_non_negative(
    hysteresis_distance: float,
) -> None:
    with pytest.raises(ValueError, match="Hysteresis distance"):
        LineCounter(
            LINE_START,
            LINE_END,
            cooldown_seconds=2.0,
            hysteresis_distance=hysteresis_distance,
        )
