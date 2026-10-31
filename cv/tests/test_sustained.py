import pytest

from cv.sustained import SustainedPresence


def make_presence() -> SustainedPresence:
    return SustainedPresence(
        minimum_seconds=5.0,
        min_confidence=0.5,
        max_gap_seconds=1.0,
    )


def test_brief_appearance_is_not_confirmed() -> None:
    presence = make_presence()

    assert not presence.update(1, 0.0, 0.9)
    assert not presence.update(1, 1.0, 0.9)


def test_long_presence_is_confirmed() -> None:
    presence = make_presence()

    assert not presence.update(1, 0.0, 0.9)
    assert not presence.update(1, 1.0, 0.9)
    assert not presence.update(1, 2.0, 0.9)
    assert not presence.update(1, 3.0, 0.9)
    assert not presence.update(1, 4.0, 0.9)
    assert presence.update(1, 5.0, 0.9)


def test_gap_within_limit_preserves_presence() -> None:
    presence = make_presence()

    assert not presence.update(1, 0.0, 0.9)
    assert not presence.update(1, 1.0, 0.9)
    assert not presence.update(1, 2.0, 0.9)
    assert not presence.update(1, 3.0, 0.9)
    assert not presence.update(1, 3.5, 0.9)
    assert not presence.update(1, 4.5, 0.9)
    assert presence.update(1, 5.0, 0.9)


def test_gap_over_limit_resets_presence_duration() -> None:
    presence = make_presence()

    assert not presence.update(1, 0.0, 0.9)
    assert not presence.update(1, 1.0, 0.9)
    assert not presence.update(1, 3.0, 0.9)
    assert not presence.update(1, 4.0, 0.9)
    assert not presence.update(1, 5.0, 0.9)
    assert not presence.update(1, 6.0, 0.9)
    assert not presence.update(1, 7.0, 0.9)
    assert presence.update(1, 8.0, 0.9)


def test_low_mean_confidence_is_not_confirmed() -> None:
    presence = make_presence()

    assert not presence.update(1, 0.0, 0.4)
    assert not presence.update(1, 1.0, 0.4)
    assert not presence.update(1, 2.0, 0.4)
    assert not presence.update(1, 3.0, 0.4)
    assert not presence.update(1, 4.0, 0.4)
    assert not presence.update(1, 5.0, 0.4)


@pytest.mark.parametrize(
    ("minimum_seconds", "min_confidence", "max_gap_seconds"),
    [
        (0.0, 0.5, 1.0),
        (5.0, -0.1, 1.0),
        (5.0, 0.5, -0.1),
        (float("nan"), 0.5, 1.0),
    ],
)
def test_invalid_configuration_is_rejected(
    minimum_seconds: float,
    min_confidence: float,
    max_gap_seconds: float,
) -> None:
    with pytest.raises(ValueError):
        SustainedPresence(
            minimum_seconds,
            min_confidence,
            max_gap_seconds,
        )
