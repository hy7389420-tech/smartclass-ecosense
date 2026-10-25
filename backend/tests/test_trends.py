import pytest

from app.services.trends import compare_outside_duration


def test_trend_reports_insufficient_history():
    result = compare_outside_duration([0, 15, 0], [1.0, 2.0], min_history=3)

    assert result.status == "insufficient_history"
    assert result.current_average_minutes == 5
    assert result.previous_average_minutes is None
    assert result.history_count == 2
    assert result.history_required == 3


def test_trend_compares_average_outside_duration():
    higher = compare_outside_duration([15, 15, 0], [1, 2, 3], min_history=3)
    not_higher = compare_outside_duration([1, 2, 3], [1, 2, 3], min_history=3)

    assert higher.status == "higher"
    assert higher.current_average_minutes == 10
    assert higher.previous_average_minutes == 2
    assert not_higher.status == "not_higher"


def test_trend_rejects_negative_values_or_invalid_history_setting():
    with pytest.raises(ValueError, match="cannot be negative"):
        compare_outside_duration([-1], [1, 2, 3])
    with pytest.raises(ValueError, match="min_history must be positive"):
        compare_outside_duration([1], [], min_history=0)
