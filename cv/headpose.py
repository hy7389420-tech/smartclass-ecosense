import math
from dataclasses import dataclass
from typing import Literal, Sequence

Orientation = Literal["facing_front", "facing_away"]


@dataclass(frozen=True)
class HeadPoseWindowResult:
    faces_detected_mean: float
    front_facing_ratio: float | None


def classify_yaw(yaw_degrees: float, front_threshold_degrees: float) -> Orientation:
    if not math.isfinite(yaw_degrees):
        raise ValueError("yaw_degrees must be finite")
    if (
        not math.isfinite(front_threshold_degrees)
        or not 0.0 <= front_threshold_degrees <= 180.0
    ):
        raise ValueError("front_threshold_degrees must be between 0 and 180")
    return (
        "facing_front"
        if abs(yaw_degrees) <= front_threshold_degrees
        else "facing_away"
    )


def yaw_degrees_from_transformation_matrix(
    matrix: Sequence[Sequence[float]],
) -> float:
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ValueError("transformation matrix must be 4 by 4")
    if any(not math.isfinite(value) for row in matrix for value in row):
        raise ValueError("transformation matrix values must be finite")

    return math.degrees(math.atan2(matrix[0][2], matrix[2][2]))


def aggregate_headpose_window(
    frame_yaws: Sequence[Sequence[float]],
    front_threshold_degrees: float,
) -> HeadPoseWindowResult:
    if not frame_yaws:
        raise ValueError("frame_yaws must contain at least one analyzed frame")

    face_count = 0
    front_count = 0
    for yaw_values in frame_yaws:
        for yaw in yaw_values:
            if classify_yaw(yaw, front_threshold_degrees) == "facing_front":
                front_count += 1
            face_count += 1

    return HeadPoseWindowResult(
        faces_detected_mean=sum(len(yaws) for yaws in frame_yaws) / len(frame_yaws),
        front_facing_ratio=front_count / face_count if face_count else None,
    )
