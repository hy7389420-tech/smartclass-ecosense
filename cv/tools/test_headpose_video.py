import argparse
import math
from pathlib import Path

import cv2

from cv.config import HEAD_POSE_FRONT_DEGREES, HEAD_POSE_WINDOW_SECONDS
from cv.headpose import aggregate_headpose_window
from cv.headpose_capture import HeadPoseEstimator


def run_video(video_path: Path) -> None:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Could not open recorded video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(fps) or fps <= 0:
        capture.release()
        raise RuntimeError("Video must provide a finite, positive frame rate")

    frame_index = 0
    window_index: int | None = None
    window_yaws: list[list[float]] = []
    try:
        with HeadPoseEstimator() as estimator:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                timestamp_seconds = frame_index / fps
                current_window = int(timestamp_seconds // HEAD_POSE_WINDOW_SECONDS)
                if window_index is not None and current_window != window_index:
                    print_window(
                        window_index,
                        window_yaws,
                        (window_index + 1) * HEAD_POSE_WINDOW_SECONDS,
                    )
                    window_yaws = []
                window_index = current_window

                frame_yaws = estimator.process_frame(
                    frame,
                    round(timestamp_seconds * 1000),
                )
                if frame_yaws is not None:
                    window_yaws.append(frame_yaws)
                frame_index += 1
    finally:
        capture.release()

    if window_index is not None:
        print_window(window_index, window_yaws, frame_index / fps)


def print_window(
    window_index: int,
    frame_yaws: list[list[float]],
    window_end: float,
) -> None:
    result = aggregate_headpose_window(frame_yaws, HEAD_POSE_FRONT_DEGREES)
    window_start = window_index * HEAD_POSE_WINDOW_SECONDS
    print(
        f"window={window_start:.0f}-{window_end:.0f}s "
        f"faces_detected_mean={result.faces_detected_mean:.3f} "
        f"front_facing_ratio={result.front_facing_ratio}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print head-orientation estimates for a recorded video."
    )
    parser.add_argument("video_path", type=Path)
    args = parser.parse_args()
    run_video(args.video_path)


if __name__ == "__main__":
    main()
