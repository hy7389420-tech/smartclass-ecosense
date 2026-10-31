import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

WINDOW_DURATION = timedelta(minutes=5)
ACTIVITY_LEVELS = (
    0.35,
    0.40,
    0.45,
    0.50,
    0.98,
    0.25,
    0.50,
    0.45,
    0.20,
    0.18,
    0.15,
    0.12,
)


def generate_activity_sample(output_path: Path) -> int:
    start = datetime(2030, 1, 1, 10, tzinfo=UTC)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for index, level in enumerate(ACTIVITY_LEVELS):
            window_start = start + index * WINDOW_DURATION
            record = {
                "window_start": window_start.isoformat(),
                "window_end": (window_start + WINDOW_DURATION).isoformat(),
                "classroom_id": 1,
                "lecture_id": 1,
                "movement_level": level,
                "inactivity_seconds": WINDOW_DURATION.total_seconds() * (1 - level),
                "front_facing_ratio": level,
                "audio_level_db_mean": -120 + 120 * level,
                "voice_activity_ratio": level,
            }
            file.write(json.dumps(record) + "\n")
    return len(ACTIVITY_LEVELS)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write 12 synthetic aggregate activity windows as JSONL."
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("activity_windows.jsonl"),
    )
    output_path = parser.parse_args().output
    written = generate_activity_sample(output_path)
    print(f"Wrote {written} synthetic activity windows to {output_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
