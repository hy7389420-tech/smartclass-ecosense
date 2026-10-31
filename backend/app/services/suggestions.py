from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from app.services.fusion import (
    EngagementSummary,
    FusedActivityWindow,
    LowActivityRun,
    analyze_activity,
    fusion_config_from_settings,
    load_activity_windows,
)
from app.services.neutral_text import assert_neutral_text

if TYPE_CHECKING:
    from app.config import Settings

SuggestionSeverity = Literal["info", "consider"]
ESTIMATE_NOTE = "Estimate based on observable indicators."
TEXT_FOOTER = (
    "This is an estimate based on observable indicators. Please use your own judgment."
)


@dataclass(frozen=True, slots=True)
class SuggestionConfig:
    voice_low_threshold: float
    voice_min_windows: int
    movement_spike_threshold: float
    noise_threshold_dbfs: float
    decline_last_windows: int
    min_valid_windows: int
    max_suggestions: int


@dataclass(frozen=True, slots=True)
class SuggestionProposal:
    rule_id: str
    title: str
    text: str
    evidence: dict[str, str | float | int | None]
    severity: SuggestionSeverity
    signals_used: tuple[str, ...]
    estimate_note: str
    status: Literal["pending"]


def suggestion_config_from_settings(settings: Settings) -> SuggestionConfig:
    return SuggestionConfig(
        voice_low_threshold=settings.activity_voice_low_threshold,
        voice_min_windows=settings.activity_voice_min_windows,
        movement_spike_threshold=settings.activity_movement_spike_threshold,
        noise_threshold_dbfs=settings.activity_noise_threshold_dbfs,
        decline_last_windows=settings.activity_decline_last_windows,
        min_valid_windows=(
            settings.activity_decline_last_windows
            + settings.activity_decline_min_baseline_windows
        ),
        max_suggestions=settings.activity_max_suggestions,
    )


def generate_suggestions(
    summary: EngagementSummary, config: SuggestionConfig
) -> tuple[SuggestionProposal, ...]:
    _validate_config(config)
    if summary.valid_window_count < config.min_valid_windows:
        info = _rule_r6(summary)
        return (info,)

    proposals = [
        proposal
        for proposal in (
            _rule_r1(summary, config),
            _rule_r2(summary),
            _rule_r3(summary, config),
            _rule_r4(summary, config),
            _rule_r5(summary),
        )
        if proposal is not None
    ]
    unique_by_rule = {proposal.rule_id: proposal for proposal in proposals}
    ordered = sorted(
        unique_by_rule.values(),
        key=lambda proposal: (
            0 if proposal.severity == "consider" else 1,
            proposal.rule_id,
        ),
    )
    return tuple(ordered[: config.max_suggestions])


def _rule_r1(
    summary: EngagementSummary, config: SuggestionConfig
) -> SuggestionProposal | None:
    decline = summary.decline
    valid_windows = [
        window for window in summary.windows if window.estimate is not None
    ]
    if decline.status != "detected":
        return None
    baseline_windows = valid_windows[: -config.decline_last_windows]
    recent_windows = valid_windows[-config.decline_last_windows :]
    if not baseline_windows or not recent_windows:
        return None
    return _proposal(
        "R1",
        "Consider a short quiz or quick poll",
        (
            "The observable activity level fell from "
            f"{decline.baseline_estimate:.2f} to "
            f"{decline.recent_estimate:.2f}. Consider a short quiz or quick poll."
        ),
        [*baseline_windows, *recent_windows],
        {
            "baseline_estimate": decline.baseline_estimate,
            "recent_estimate": decline.recent_estimate,
            "drop": decline.drop,
        },
        "consider",
    )


def _rule_r2(summary: EngagementSummary) -> SuggestionProposal | None:
    middle_runs = [
        (run, _windows_for_run(summary.windows, run))
        for run in summary.low_runs
        if _is_middle_run(summary.windows, run)
    ]
    selected = max(
        middle_runs,
        key=lambda item: item[0].window_count,
        default=None,
    )
    if selected is None:
        return None
    run, run_windows = selected
    return _proposal(
        "R2",
        "Consider a group discussion or pair activity",
        (
            "The observable activity level stayed low for "
            f"{run.window_count} windows (average estimate "
            f"{run.average_estimate:.2f}). Consider a group discussion or "
            "pair activity."
        ),
        run_windows,
        {
            "window_count": run.window_count,
            "average_estimate": run.average_estimate,
        },
        "consider",
    )


def _rule_r3(
    summary: EngagementSummary, config: SuggestionConfig
) -> SuggestionProposal | None:
    low_voice_windows = [
        window
        for window in summary.windows
        if window.estimate is not None
        and window.voice_activity_ratio is not None
        and window.voice_activity_ratio < config.voice_low_threshold
        and window.movement_level is not None
        and window.movement_level <= config.movement_spike_threshold
    ]
    if len(low_voice_windows) < config.voice_min_windows:
        return None
    voice_average = sum(
        window.voice_activity_ratio
        for window in low_voice_windows
        if window.voice_activity_ratio is not None
    ) / len(low_voice_windows)
    movement_average = sum(
        window.movement_level
        for window in low_voice_windows
        if window.movement_level is not None
    ) / len(low_voice_windows)
    return _proposal(
        "R3",
        "Consider asking an interactive question",
        (
            "Voice activity was low while movement stayed within the normal "
            f"range (voice ratio {voice_average:.2f}; movement average "
            f"{movement_average:.2f}). Consider asking the class an "
            "interactive question."
        ),
        low_voice_windows,
        {
            "voice_activity_ratio_average": voice_average,
            "movement_level_average": movement_average,
            "window_count": len(low_voice_windows),
        },
        "consider",
    )


def _rule_r4(
    summary: EngagementSummary, config: SuggestionConfig
) -> SuggestionProposal | None:
    qualifying_runs = []
    for run in summary.low_runs:
        run_windows = _windows_for_run(summary.windows, run)
        movement_values = [
            window.movement_level
            for window in run_windows
            if window.movement_level is not None
        ]
        audio_values = [
            window.audio_level_db_mean
            for window in run_windows
            if window.audio_level_db_mean is not None
        ]
        movement_max = max(movement_values, default=None)
        audio_max = max(audio_values, default=None)
        movement_spike = (
            movement_max is not None and movement_max >= config.movement_spike_threshold
        )
        noise_spike = audio_max is not None and audio_max >= config.noise_threshold_dbfs
        if movement_spike or noise_spike:
            qualifying_runs.append(
                (run, run_windows, movement_max, audio_max, movement_spike, noise_spike)
            )
    if not qualifying_runs:
        return None
    run, run_windows, movement_max, audio_max, movement_spike, noise_spike = max(
        qualifying_runs, key=lambda item: item[0].window_count
    )

    indicators = []
    if movement_spike:
        indicators.append(f"movement max {_format_number(movement_max)}")
    if noise_spike:
        indicators.append(f"audio peak {_format_dbfs(audio_max)}")
    return _proposal(
        "R4",
        "Consider a short break or pace change",
        (
            "A low observable activity level coincided with "
            f"{' and '.join(indicators)}. Consider a short break or pace change."
        ),
        run_windows,
        {
            "low_run_windows": run.window_count,
            "average_estimate": run.average_estimate,
            "movement_level_max": movement_max,
            "audio_level_max_dbfs": audio_max,
        },
        "consider",
    )


def _rule_r5(summary: EngagementSummary) -> SuggestionProposal | None:
    peak_then_low = [
        (peak, run)
        for peak in summary.peaks
        for run in summary.low_runs
        if peak.timestamp < run.start
    ]
    if not peak_then_low:
        return None
    peak, run = max(
        peak_then_low,
        key=lambda item: (item[0].estimate, item[1].window_count),
    )
    evidence_windows = [
        window
        for window in summary.windows
        if window.window_start >= peak.timestamp
        and window.window_end <= run.end
        and window.estimate is not None
    ]
    return _proposal(
        "R5",
        "Consider a practical example or demonstration",
        (
            "The observable activity level fell from an earlier peak "
            f"of {peak.estimate:.2f} to {run.average_estimate:.2f} during a "
            "later low period. Consider a practical example or demonstration."
        ),
        evidence_windows,
        {
            "peak_estimate": peak.estimate,
            "low_run_average": run.average_estimate,
            "drop": round(peak.estimate - run.average_estimate, 4),
        },
        "consider",
    )


def _rule_r6(summary: EngagementSummary) -> SuggestionProposal:
    return _proposal(
        "R6",
        "Not enough data",
        (
            "There is not enough aggregate activity data "
            f"({summary.valid_window_count} valid windows) to make a suggestion."
        ),
        summary.windows,
        {"valid_window_count": summary.valid_window_count},
        "info",
    )


def _validate_config(config: SuggestionConfig) -> None:
    if not all(
        isfinite(value)
        for value in (
            config.voice_low_threshold,
            config.movement_spike_threshold,
            config.noise_threshold_dbfs,
        )
    ):
        raise ValueError("Suggestion thresholds must contain only finite numbers.")
    if not 0 <= config.voice_low_threshold <= 1:
        raise ValueError("voice_low_threshold must be between 0 and 1.")
    if not 0 <= config.movement_spike_threshold <= 1:
        raise ValueError("movement_spike_threshold must be between 0 and 1.")
    if config.voice_min_windows < 1:
        raise ValueError("voice_min_windows must be at least one.")
    if config.decline_last_windows < 1 or config.min_valid_windows < 1:
        raise ValueError("Suggestion trend windows must be at least one.")
    if config.max_suggestions < 1:
        raise ValueError("max_suggestions must be at least one.")


def _windows_for_run(
    windows: tuple[FusedActivityWindow, ...], run: LowActivityRun
) -> list[FusedActivityWindow]:
    return [
        window
        for window in windows
        if window.label == "low"
        and run.start <= window.window_start
        and window.window_end <= run.end
    ]


def _is_middle_run(
    windows: tuple[FusedActivityWindow, ...], run: LowActivityRun
) -> bool:
    return any(
        window.estimate is not None and window.window_end <= run.start
        for window in windows
    ) and any(
        window.estimate is not None and window.window_start >= run.end
        for window in windows
    )


def _proposal(
    rule_id: str,
    title: str,
    body: str,
    windows: list[FusedActivityWindow] | tuple[FusedActivityWindow, ...],
    evidence: dict[str, str | float | int | None],
    severity: SuggestionSeverity,
) -> SuggestionProposal:
    ordered_windows = sorted(windows, key=lambda window: window.window_start)
    first = ordered_windows[0] if ordered_windows else None
    last = ordered_windows[-1] if ordered_windows else None
    evidence_with_range = {
        **evidence,
        "window_start": first.window_start.isoformat() if first else None,
        "window_end": last.window_end.isoformat() if last else None,
    }
    signals_used = tuple(
        sorted(
            {
                name
                for window in ordered_windows
                for name, value in window.signals.items()
                if value is not None
            }
        )
    )
    text_body = body
    if first is not None and last is not None:
        text_body += (
            " Evidence window: "
            f"{first.window_start.isoformat()} to {last.window_end.isoformat()}."
        )
    text = assert_neutral_text(f"{text_body} {TEXT_FOOTER}")
    return SuggestionProposal(
        rule_id=rule_id,
        title=assert_neutral_text(title),
        text=text,
        evidence=evidence_with_range,
        severity=severity,
        signals_used=signals_used,
        estimate_note=ESTIMATE_NOTE,
        status="pending",
    )


def _format_number(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "not available"


def _format_dbfs(value: float | None) -> str:
    return f"{value:.1f} dBFS" if value is not None else "not available"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate neutral teaching suggestions from activity windows."
    )
    parser.add_argument("jsonl_path", type=Path)
    args = parser.parse_args(argv)
    try:
        from app.config import get_settings

        settings = get_settings()
        summary = analyze_activity(
            load_activity_windows(args.jsonl_path),
            fusion_config_from_settings(),
        )
        proposals = generate_suggestions(
            summary,
            suggestion_config_from_settings(settings),
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps([asdict(proposal) for proposal in proposals], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
