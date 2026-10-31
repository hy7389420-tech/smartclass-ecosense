from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import ApiError
from app.models import ActivityWindow, Lecture, Suggestion
from app.schemas.activity import (
    ActivityIngestResponse,
    ActivityPeakRead,
    ActivityWindowRead,
    ActivityWindowWrite,
    DeclineRead,
    EngagementRead,
    EngagementWindowRead,
    LowActivityRunRead,
)
from app.schemas.resources import normalize_output_datetime
from app.schemas.suggestions import SuggestionRead
from app.services.fusion import (
    ActivitySignals,
    EngagementSummary,
    FusionConfig,
    analyze_activity,
)
from app.services.suggestions import (
    generate_suggestions,
    suggestion_config_from_settings,
)

ESTIMATE_NOTE = "estimate based on observable indicators"


def store_activity_windows(
    session: Session, payloads: Sequence[ActivityWindowWrite]
) -> ActivityIngestResponse:
    settings = get_settings()
    if len(payloads) > settings.activity_max_batch_size:
        raise ApiError(
            422,
            "ACTIVITY_BATCH_TOO_LARGE",
            "Activity window batch exceeds the configured maximum.",
        )

    lecture_cache: dict[int, Lecture] = {}
    seen: set[tuple[int, datetime]] = set()
    batch_ranges: dict[int, list[tuple[datetime, datetime]]] = {}
    results: list[ActivityWindow] = []
    duplicate_count = 0

    if not payloads:
        raise ApiError(
            422,
            "EMPTY_ACTIVITY_BATCH",
            "At least one activity window is required.",
        )

    for payload in payloads:
        key = (payload.lecture_id, payload.window_start)
        if key in seen:
            raise ApiError(
                422,
                "DUPLICATE_ACTIVITY_WINDOW_IN_BATCH",
                "A batch cannot contain multiple windows with the same start time.",
            )
        seen.add(key)

        lecture = lecture_cache.get(payload.lecture_id)
        if lecture is None:
            lecture = session.get(Lecture, payload.lecture_id)
            if lecture is None:
                raise ApiError(404, "LECTURE_NOT_FOUND", "Lecture was not found.")
            lecture_cache[payload.lecture_id] = lecture
        if lecture.status not in {"live", "completed"}:
            raise ApiError(
                409,
                "LECTURE_NOT_ACTIVE",
                "Activity windows can be stored only for live or completed lectures.",
            )
        lecture_start = normalize_output_datetime(lecture.start_time)
        lecture_end = normalize_output_datetime(lecture.end_time)
        if payload.window_start < lecture_start or payload.window_end > lecture_end:
            raise ApiError(
                422,
                "ACTIVITY_WINDOW_OUTSIDE_LECTURE",
                "Activity window must be inside the scheduled lecture time.",
            )

        existing = session.scalar(
            select(ActivityWindow).where(
                ActivityWindow.lecture_id == payload.lecture_id,
                ActivityWindow.window_start == payload.window_start,
            )
        )
        if existing is not None:
            if not _matches_payload(existing, payload):
                raise ApiError(
                    409,
                    "ACTIVITY_WINDOW_CONFLICT",
                    "An activity window with this start time already has different data.",
                )
            duplicate_count += 1
            results.append(existing)
            continue

        overlapping = session.scalar(
            select(ActivityWindow.id)
            .where(
                ActivityWindow.lecture_id == payload.lecture_id,
                ActivityWindow.window_start < payload.window_end,
                ActivityWindow.window_end > payload.window_start,
            )
            .limit(1)
        )
        if overlapping is not None or any(
            start < payload.window_end and end > payload.window_start
            for start, end in batch_ranges.get(payload.lecture_id, [])
        ):
            raise ApiError(
                409,
                "ACTIVITY_WINDOW_OVERLAP",
                "Activity windows for a lecture cannot overlap.",
            )

        row = ActivityWindow(
            lecture_id=payload.lecture_id,
            window_start=payload.window_start,
            window_end=payload.window_end,
            movement_level=payload.movement_level,
            inactivity_seconds=payload.inactivity_seconds,
            front_facing_ratio=payload.front_facing_ratio,
            audio_level_db_mean=payload.audio_level_db_mean,
            voice_activity_ratio=payload.voice_activity_ratio,
            source=payload.source,
        )
        session.add(row)
        results.append(row)
        batch_ranges.setdefault(payload.lecture_id, []).append(
            (payload.window_start, payload.window_end)
        )

    session.flush()
    return ActivityIngestResponse(
        stored_count=len(payloads) - duplicate_count,
        duplicate_count=duplicate_count,
        windows=[ActivityWindowRead.model_validate(row) for row in results],
    )


def get_lecture_engagement(session: Session, lecture_id: int) -> EngagementRead:
    _, summary = _get_activity_summary(session, lecture_id)
    return _engagement_read(lecture_id, summary)


def get_lecture_suggestions(session: Session, lecture_id: int) -> list[SuggestionRead]:
    _, summary = _get_activity_summary(session, lecture_id)
    proposals = generate_suggestions(
        summary,
        suggestion_config_from_settings(get_settings()),
    )
    if not proposals:
        return []

    existing_rows = list(
        session.scalars(select(Suggestion).where(Suggestion.lecture_id == lecture_id))
    )
    existing_by_rule = {row.rule_id: row for row in existing_rows}
    result: list[Suggestion] = []
    for proposal in proposals:
        row = existing_by_rule.get(proposal.rule_id)
        if row is None:
            row = Suggestion(
                lecture_id=lecture_id,
                rule_id=proposal.rule_id,
                title=proposal.title,
                text=proposal.text,
                evidence_json={
                    **proposal.evidence,
                    "signals_used": list(proposal.signals_used),
                    "estimate_note": proposal.estimate_note,
                },
                severity={"info": "low", "consider": "medium"}[proposal.severity],
                status=proposal.status,
            )
            session.add(row)
        result.append(row)
    session.flush()
    return [SuggestionRead.model_validate(row) for row in result]


def _get_activity_summary(
    session: Session, lecture_id: int
) -> tuple[Lecture, EngagementSummary]:
    lecture = session.get(Lecture, lecture_id)
    if lecture is None:
        raise ApiError(404, "LECTURE_NOT_FOUND", "Lecture was not found.")
    rows = list(
        session.scalars(
            select(ActivityWindow)
            .where(ActivityWindow.lecture_id == lecture_id)
            .order_by(ActivityWindow.window_start, ActivityWindow.id)
        )
    )
    summary = analyze_activity(
        [
            ActivitySignals(
                window_start=normalize_output_datetime(row.window_start),
                window_end=normalize_output_datetime(row.window_end),
                movement_level=row.movement_level,
                inactivity_seconds=row.inactivity_seconds,
                front_facing_ratio=row.front_facing_ratio,
                audio_level_db_mean=row.audio_level_db_mean,
                voice_activity_ratio=row.voice_activity_ratio,
            )
            for row in rows
        ],
        _fusion_config(get_settings()),
    )
    return lecture, summary


def _fusion_config(settings: Settings) -> FusionConfig:
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
        decline_min_baseline_windows=settings.activity_decline_min_baseline_windows,
        decline_threshold=settings.activity_decline_threshold,
    )


def _engagement_read(lecture_id: int, summary: EngagementSummary) -> EngagementRead:
    return EngagementRead(
        lecture_id=lecture_id,
        estimate_note=ESTIMATE_NOTE,
        windows=[
            EngagementWindowRead(
                window_start=window.window_start,
                window_end=window.window_end,
                estimate=window.estimate,
                label=window.label,
                available_signals=window.available_signals,
                signals=window.signals,
            )
            for window in summary.windows
        ],
        average_estimate=summary.average_estimate,
        peaks=[
            ActivityPeakRead(timestamp=peak.timestamp, estimate=peak.estimate)
            for peak in summary.peaks
        ],
        low_runs=[
            LowActivityRunRead(
                start=run.start,
                end=run.end,
                window_count=run.window_count,
                average_estimate=run.average_estimate,
            )
            for run in summary.low_runs
        ],
        decline=DeclineRead(
            status=summary.decline.status,
            baseline_estimate=summary.decline.baseline_estimate,
            recent_estimate=summary.decline.recent_estimate,
            drop=summary.decline.drop,
        ),
        peak_drop_detected=summary.peak_drop_detected,
        peak_estimate=summary.peak_estimate,
        recent_estimate=summary.recent_estimate,
        voice_activity_average=summary.voice_activity_average,
        voice_activity_windows=summary.voice_activity_windows,
        movement_level_max=summary.movement_level_max,
        audio_level_average_dbfs=summary.audio_level_average_dbfs,
        valid_window_count=summary.valid_window_count,
        insufficient_window_count=summary.insufficient_window_count,
    )


def _matches_payload(row: ActivityWindow, payload: ActivityWindowWrite) -> bool:
    return (
        normalize_output_datetime(row.window_start) == payload.window_start
        and normalize_output_datetime(row.window_end) == payload.window_end
        and row.movement_level == payload.movement_level
        and row.inactivity_seconds == payload.inactivity_seconds
        and row.front_facing_ratio == payload.front_facing_ratio
        and row.audio_level_db_mean == payload.audio_level_db_mean
        and row.voice_activity_ratio == payload.voice_activity_ratio
        and row.source == payload.source
    )
