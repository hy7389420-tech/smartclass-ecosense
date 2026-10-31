import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from math import isfinite
from pathlib import Path
from statistics import fmean, pstdev
from typing import Literal

SignalName = Literal[
    "movement",
    "inactivity_inverted",
    "head_front",
    "voice_activity",
    "audio_level",
]
EstimateLabel = Literal["high", "medium", "low", "insufficient_data"]
DeclineStatus = Literal["detected", "not_detected", "insufficient_data"]


@dataclass(frozen=True, slots=True)
class ActivitySignals:
    window_start: datetime
    window_end: datetime
    movement_level: float | None = None
    inactivity_seconds: float | None = None
    front_facing_ratio: float | None = None
    audio_level_db_mean: float | None = None
    voice_activity_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class FusionConfig:
    movement_weight: float
    inactivity_weight: float
    head_weight: float
    voice_weight: float
    audio_weight: float
    movement_min: float
    movement_max: float
    front_min: float
    front_max: float
    voice_min: float
    voice_max: float
    audio_min_dbfs: float
    audio_max_dbfs: float
    min_signals: int
    low_cutoff: float
    high_cutoff: float
    low_run_windows: int
    smoothing_windows: int
    min_windows_for_stats: int
    peak_z: float
    decline_last_windows: int
    decline_min_baseline_windows: int
    decline_threshold: float


@dataclass(frozen=True, slots=True)
class FusedActivityWindow:
    window_start: datetime
    window_end: datetime
    estimate: float | None
    label: EstimateLabel
    available_signals: int
    signals: dict[SignalName, float | None]
    movement_level: float | None
    audio_level_db_mean: float | None
    voice_activity_ratio: float | None


@dataclass(frozen=True, slots=True)
class LowActivityRun:
    start: datetime
    end: datetime
    window_count: int
    average_estimate: float


@dataclass(frozen=True, slots=True)
class ActivityPeak:
    timestamp: datetime
    estimate: float


@dataclass(frozen=True, slots=True)
class DeclineAnalysis:
    status: DeclineStatus
    baseline_estimate: float | None
    recent_estimate: float | None
    drop: float | None


@dataclass(frozen=True, slots=True)
class EngagementSummary:
    windows: tuple[FusedActivityWindow, ...]
    average_estimate: float | None
    peaks: tuple[ActivityPeak, ...]
    low_runs: tuple[LowActivityRun, ...]
    decline: DeclineAnalysis
    peak_drop_detected: bool
    peak_estimate: float | None
    recent_estimate: float | None
    voice_activity_average: float | None
    voice_activity_windows: int
    movement_level_max: float | None
    audio_level_average_dbfs: float | None
    valid_window_count: int
    insufficient_window_count: int


def analyze_activity(
    windows: Sequence[ActivitySignals], config: FusionConfig
) -> EngagementSummary:
    _validate_config(config)
    ordered_windows = sorted(windows, key=lambda item: item.window_start)
    fused = _smooth_windows(
        tuple(_fuse_window(window, config) for window in ordered_windows),
        config.smoothing_windows,
        config.low_cutoff,
        config.high_cutoff,
    )
    valid = [window for window in fused if window.estimate is not None]
    estimates = [window.estimate for window in valid if window.estimate is not None]
    average = sum(estimates) / len(estimates) if estimates else None
    peaks = _find_peaks(valid, config)
    low_runs = _low_activity_runs(fused, config.low_run_windows)
    decline = _analyze_decline(valid, config)

    peak_estimate: float | None = None
    recent_estimate: float | None = None
    peak_drop_detected = False
    minimum_decline_windows = (
        config.decline_last_windows + config.decline_min_baseline_windows
    )
    if len(valid) >= minimum_decline_windows:
        earlier = valid[: -config.decline_last_windows]
        recent = valid[-config.decline_last_windows :]
        earlier_values = [
            window.estimate for window in earlier if window.estimate is not None
        ]
        recent_values = [
            window.estimate for window in recent if window.estimate is not None
        ]
        if earlier_values and recent_values:
            peak_estimate = max(earlier_values)
            recent_estimate = sum(recent_values) / len(recent_values)
            peak_drop_detected = (
                peak_estimate - recent_estimate >= config.decline_threshold
            )

    voice_values = [
        window.voice_activity_ratio
        for window in ordered_windows
        if window.voice_activity_ratio is not None
    ]
    movement_values = [
        window.movement_level
        for window in ordered_windows
        if window.movement_level is not None
    ]
    audio_values = [
        window.audio_level_db_mean
        for window in ordered_windows
        if window.audio_level_db_mean is not None
    ]
    return EngagementSummary(
        windows=fused,
        average_estimate=round(average, 4) if average is not None else None,
        peaks=peaks,
        low_runs=low_runs,
        decline=decline,
        peak_drop_detected=peak_drop_detected,
        peak_estimate=(round(peak_estimate, 4) if peak_estimate is not None else None),
        recent_estimate=(
            round(recent_estimate, 4) if recent_estimate is not None else None
        ),
        voice_activity_average=(
            round(sum(voice_values) / len(voice_values), 4) if voice_values else None
        ),
        voice_activity_windows=len(voice_values),
        movement_level_max=max(movement_values) if movement_values else None,
        audio_level_average_dbfs=(
            round(sum(audio_values) / len(audio_values), 2) if audio_values else None
        ),
        valid_window_count=len(valid),
        insufficient_window_count=len(fused) - len(valid),
    )


def _fuse_window(window: ActivitySignals, config: FusionConfig) -> FusedActivityWindow:
    if (
        window.window_start.tzinfo is None
        or window.window_start.utcoffset() is None
        or window.window_end.tzinfo is None
        or window.window_end.utcoffset() is None
        or window.window_end <= window.window_start
    ):
        raise ValueError("Activity windows require timezone-aware increasing times.")
    duration = (window.window_end - window.window_start).total_seconds()
    if window.inactivity_seconds is not None and (
        not isfinite(window.inactivity_seconds)
        or not 0 <= window.inactivity_seconds <= duration
    ):
        raise ValueError("inactivity_seconds must fit inside its activity window.")

    weights = {
        "movement": config.movement_weight,
        "inactivity_inverted": config.inactivity_weight,
        "head_front": config.head_weight,
        "voice_activity": config.voice_weight,
        "audio_level": config.audio_weight,
    }
    normalized: dict[SignalName, float | None] = {
        "movement": _normalize(
            window.movement_level, config.movement_min, config.movement_max
        ),
        "inactivity_inverted": (
            1 - min(max(window.inactivity_seconds / duration, 0), 1)
            if window.inactivity_seconds is not None
            else None
        ),
        "head_front": _normalize(
            window.front_facing_ratio, config.front_min, config.front_max
        ),
        "voice_activity": _normalize(
            window.voice_activity_ratio, config.voice_min, config.voice_max
        ),
        "audio_level": _normalize(
            window.audio_level_db_mean,
            config.audio_min_dbfs,
            config.audio_max_dbfs,
        ),
    }
    available = [
        (name, value, weights[name])
        for name, value in normalized.items()
        if value is not None and weights[name] > 0
    ]
    if len(available) < config.min_signals:
        return FusedActivityWindow(
            window_start=window.window_start,
            window_end=window.window_end,
            estimate=None,
            label="insufficient_data",
            available_signals=len(available),
            signals=normalized,
            movement_level=window.movement_level,
            audio_level_db_mean=window.audio_level_db_mean,
            voice_activity_ratio=window.voice_activity_ratio,
        )
    weight_total = sum(weight for _, _, weight in available)
    estimate = sum(value * weight for _, value, weight in available) / weight_total
    label = _estimate_label(estimate, config.low_cutoff, config.high_cutoff)
    return FusedActivityWindow(
        window_start=window.window_start,
        window_end=window.window_end,
        estimate=round(estimate, 4),
        label=label,
        available_signals=len(available),
        signals=normalized,
        movement_level=window.movement_level,
        audio_level_db_mean=window.audio_level_db_mean,
        voice_activity_ratio=window.voice_activity_ratio,
    )


def _normalize(value: float | None, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    if not isfinite(value):
        raise ValueError("Activity signal values must be finite.")
    if maximum <= minimum:
        raise ValueError("Signal normalization maximum must exceed its minimum.")
    return min(max((value - minimum) / (maximum - minimum), 0), 1)


def _validate_config(config: FusionConfig) -> None:
    numeric_values = (
        config.movement_weight,
        config.inactivity_weight,
        config.head_weight,
        config.voice_weight,
        config.audio_weight,
        config.movement_min,
        config.movement_max,
        config.front_min,
        config.front_max,
        config.voice_min,
        config.voice_max,
        config.audio_min_dbfs,
        config.audio_max_dbfs,
        config.low_cutoff,
        config.high_cutoff,
        config.peak_z,
        config.decline_threshold,
    )
    if not all(isfinite(value) for value in numeric_values):
        raise ValueError("Fusion settings must contain only finite numbers.")
    if (
        min(
            config.movement_weight,
            config.inactivity_weight,
            config.head_weight,
            config.voice_weight,
            config.audio_weight,
        )
        < 0
    ):
        raise ValueError("Fusion signal weights cannot be negative.")
    if (
        sum(
            (
                config.movement_weight,
                config.inactivity_weight,
                config.head_weight,
                config.voice_weight,
                config.audio_weight,
            )
        )
        <= 0
    ):
        raise ValueError("At least one fusion signal weight must be positive.")
    if config.min_signals < 1:
        raise ValueError("min_signals must be at least one.")
    if config.low_cutoff < 0 or config.high_cutoff > 1:
        raise ValueError("Activity cutoffs must be within 0 and 1.")
    if config.low_cutoff >= config.high_cutoff:
        raise ValueError("high_cutoff must exceed low_cutoff.")
    if config.smoothing_windows < 1:
        raise ValueError("smoothing_windows must be at least one.")
    if config.min_windows_for_stats < 2:
        raise ValueError("min_windows_for_stats must be at least two.")
    if config.peak_z < 0:
        raise ValueError("peak_z cannot be negative.")
    if config.decline_last_windows < 1 or config.decline_min_baseline_windows < 1:
        raise ValueError("Decline analysis requires recent and baseline windows.")
    if config.low_run_windows < 1:
        raise ValueError("low_run_windows must be at least one.")


def _smooth_windows(
    windows: Sequence[FusedActivityWindow],
    smoothing_windows: int,
    low_cutoff: float,
    high_cutoff: float,
) -> tuple[FusedActivityWindow, ...]:
    if smoothing_windows == 1:
        return tuple(windows)

    smoothed: list[FusedActivityWindow] = []
    recent_values: list[float] = []
    previous_end: datetime | None = None
    for window in windows:
        if window.estimate is None:
            recent_values.clear()
            previous_end = None
            smoothed.append(window)
            continue
        if previous_end != window.window_start:
            recent_values.clear()
        recent_values.append(window.estimate)
        del recent_values[:-smoothing_windows]
        estimate = round(fmean(recent_values), 4)
        smoothed.append(
            replace(
                window,
                estimate=estimate,
                label=_estimate_label(estimate, low_cutoff, high_cutoff),
            )
        )
        previous_end = window.window_end
    return tuple(smoothed)


def _estimate_label(
    estimate: float, low_cutoff: float, high_cutoff: float
) -> EstimateLabel:
    if estimate < low_cutoff:
        return "low"
    if estimate >= high_cutoff:
        return "high"
    return "medium"


def _find_peaks(
    windows: Sequence[FusedActivityWindow], config: FusionConfig
) -> tuple[ActivityPeak, ...]:
    estimates = [window.estimate for window in windows if window.estimate is not None]
    if len(estimates) < config.min_windows_for_stats:
        return ()
    threshold = fmean(estimates) + config.peak_z * pstdev(estimates)
    return tuple(
        ActivityPeak(window.window_start, window.estimate)
        for window in windows
        if window.estimate is not None
        and window.estimate >= threshold
        and window.estimate > config.high_cutoff
    )


def _low_activity_runs(
    windows: Sequence[FusedActivityWindow], minimum_windows: int
) -> tuple[LowActivityRun, ...]:
    runs: list[LowActivityRun] = []
    current: list[FusedActivityWindow] = []

    def finish_run() -> None:
        if len(current) >= minimum_windows:
            estimates = [
                window.estimate for window in current if window.estimate is not None
            ]
            runs.append(
                LowActivityRun(
                    start=current[0].window_start,
                    end=current[-1].window_end,
                    window_count=len(current),
                    average_estimate=round(sum(estimates) / len(estimates), 4),
                )
            )
        current.clear()

    for window in windows:
        if window.label == "low" and (
            not current or current[-1].window_end == window.window_start
        ):
            current.append(window)
        else:
            finish_run()
            if window.label == "low":
                current.append(window)
    finish_run()
    return tuple(runs)


def _analyze_decline(
    windows: Sequence[FusedActivityWindow], config: FusionConfig
) -> DeclineAnalysis:
    minimum_windows = config.decline_last_windows + config.decline_min_baseline_windows
    if len(windows) < minimum_windows:
        return DeclineAnalysis("insufficient_data", None, None, None)
    earlier = [
        window.estimate
        for window in windows[: -config.decline_last_windows]
        if window.estimate is not None
    ]
    recent = [
        window.estimate
        for window in windows[-config.decline_last_windows :]
        if window.estimate is not None
    ]
    if not earlier or not recent:
        return DeclineAnalysis("insufficient_data", None, None, None)
    baseline = sum(earlier) / len(earlier)
    recent_average = sum(recent) / len(recent)
    drop = baseline - recent_average
    return DeclineAnalysis(
        status="detected" if drop >= config.decline_threshold else "not_detected",
        baseline_estimate=round(baseline, 4),
        recent_estimate=round(recent_average, 4),
        drop=round(drop, 4),
    )


def load_activity_windows(path: Path) -> list[ActivitySignals]:
    windows: list[ActivitySignals] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise TypeError("each JSONL record must be an object")
                windows.append(
                    ActivitySignals(
                        window_start=_parse_datetime(record["window_start"]),
                        window_end=_parse_datetime(record["window_end"]),
                        movement_level=record.get("movement_level"),
                        inactivity_seconds=record.get("inactivity_seconds"),
                        front_facing_ratio=record.get("front_facing_ratio"),
                        audio_level_db_mean=record.get("audio_level_db_mean"),
                        voice_activity_ratio=record.get("voice_activity_ratio"),
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"{path}:{line_number}: invalid activity window: {error}"
                ) from error
    return windows


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamps must be ISO-formatted strings")
    return datetime.fromisoformat(value)


def fusion_config_from_settings() -> FusionConfig:
    from app.config import get_settings

    settings = get_settings()
    return FusionConfig(
        movement_weight=settings.activity_movement_weight,
        inactivity_weight=settings.activity_inactivity_weight,
        head_weight=settings.activity_head_weight,
        voice_weight=settings.activity_voice_weight,
        audio_weight=settings.activity_audio_weight,
        movement_min=settings.activity_movement_min,
        movement_max=settings.activity_movement_max,
        front_min=settings.activity_front_min,
        front_max=settings.activity_front_max,
        voice_min=settings.activity_voice_min,
        voice_max=settings.activity_voice_max,
        audio_min_dbfs=settings.activity_audio_min_dbfs,
        audio_max_dbfs=settings.activity_audio_max_dbfs,
        min_signals=settings.activity_min_signals,
        low_cutoff=settings.activity_low_cutoff,
        high_cutoff=settings.activity_high_cutoff,
        low_run_windows=settings.activity_low_run_windows,
        smoothing_windows=settings.activity_smoothing_windows,
        min_windows_for_stats=settings.activity_min_windows_for_stats,
        peak_z=settings.activity_peak_z,
        decline_last_windows=settings.activity_decline_last_windows,
        decline_min_baseline_windows=(settings.activity_decline_min_baseline_windows),
        decline_threshold=settings.activity_decline_threshold,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fuse aggregate activity windows and print timeline findings."
    )
    parser.add_argument("jsonl_path", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = analyze_activity(
            load_activity_windows(args.jsonl_path),
            fusion_config_from_settings(),
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            asdict(summary),
            default=lambda value: (
                value.isoformat() if isinstance(value, datetime) else str(value)
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
