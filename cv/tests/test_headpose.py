import math

import pytest

from cv.headpose import (
    aggregate_headpose_window,
    classify_yaw,
    yaw_degrees_from_transformation_matrix,
)


@pytest.mark.parametrize(
    ("yaw_degrees", "expected"),
    [
        (0.0, "facing_front"),
        (20.0, "facing_front"),
        (-20.0, "facing_front"),
        (20.01, "facing_away"),
        (-35.0, "facing_away"),
    ],
)
def test_classify_yaw(yaw_degrees: float, expected: str) -> None:
    assert classify_yaw(yaw_degrees, 20.0) == expected


def test_yaw_is_extracted_from_face_transformation_matrix() -> None:
    yaw_radians = math.radians(30.0)
    matrix = [
        [math.cos(yaw_radians), 0.0, math.sin(yaw_radians), 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [-math.sin(yaw_radians), 0.0, math.cos(yaw_radians), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]

    assert yaw_degrees_from_transformation_matrix(matrix) == pytest.approx(30.0)


def test_window_aggregation_returns_mean_faces_and_front_ratio() -> None:
    result = aggregate_headpose_window(
        frame_yaws=[[5.0, 40.0], [], [-10.0]],
        front_threshold_degrees=20.0,
    )

    assert result.faces_detected_mean == pytest.approx(1.0)
    assert result.front_facing_ratio == pytest.approx(2 / 3)


def test_no_faces_returns_null_front_facing_ratio() -> None:
    result = aggregate_headpose_window(
        frame_yaws=[[], []],
        front_threshold_degrees=20.0,
    )

    assert result.faces_detected_mean == 0.0
    assert result.front_facing_ratio is None


@pytest.mark.parametrize("yaw_degrees", [float("nan"), float("inf")])
def test_non_finite_yaw_is_rejected(yaw_degrees: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        classify_yaw(yaw_degrees, 20.0)


def test_invalid_transformation_matrix_is_rejected() -> None:
    with pytest.raises(ValueError, match="4 by 4"):
        yaw_degrees_from_transformation_matrix([[1.0, 0.0], [0.0, 1.0]])
