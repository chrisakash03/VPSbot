from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from vpsbot.config import Settings
from vpsbot.reminders.jev.client import parse_with_jev
from vpsbot.reminders.parsing import ParseError, parse_reminder_text
from vpsbot.reminders.router import should_invoke_jev
from vpsbot.reminders.schedule_spec import (
    ParseSource,
    ReviewAction,
    ScheduleSpec,
    parsed_reminder_to_spec,
    validate_schedule_spec,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    spec: ScheduleSpec | None = None
    error: str | None = None
    clarify_options: list[str] | None = None


def _apply_confidence_gate(spec: ScheduleSpec, settings: Settings) -> ScheduleSpec:
    conf = spec.confidence if spec.confidence is not None else 1.0
    if spec.source == ParseSource.FAST:
        spec.review = ReviewAction.AUTO
        return spec
    if conf < settings.jev_confidence_min:
        spec.review = ReviewAction.CLARIFY
        if not spec.review_reason:
            spec.review_reason = "I need a clearer date or schedule."
    elif conf < settings.jev_confidence_auto:
        spec.review = ReviewAction.CONFIRM
        if not spec.review_reason:
            spec.review_reason = "Please confirm this schedule."
    else:
        spec.review = ReviewAction.AUTO
    return spec


async def parse_reminder_pipeline(
    text: str,
    settings: Settings,
    now_utc: datetime | None = None,
) -> PipelineResult:
    now_utc = now_utc or datetime.now(ZoneInfo("UTC"))
    fast_result = None
    fast_error: ParseError | None = None

    try:
        fast_result = parse_reminder_text(text, settings.timezone, now_utc=now_utc)
    except ParseError as exc:
        fast_error = exc

    if not should_invoke_jev(text, fast_result, fast_error):
        if fast_result is None:
            return PipelineResult(error=str(fast_error) if fast_error else "Could not parse reminder.")
        spec = parsed_reminder_to_spec(fast_result, ParseSource.FAST)
        errors = validate_schedule_spec(spec, now_utc)
        if errors:
            return PipelineResult(error="; ".join(errors))
        return PipelineResult(spec=_apply_confidence_gate(spec, settings))

    if not settings.jev_enabled:
        if fast_result is not None:
            spec = parsed_reminder_to_spec(fast_result, ParseSource.FAST)
            return PipelineResult(spec=_apply_confidence_gate(spec, settings))
        return PipelineResult(
            error=str(fast_error) if fast_error else "Could not parse. Enable Jev for complex schedules.",
        )

    fallback_start = fast_result.fire_at_utc if fast_result else None
    try:
        spec = await parse_with_jev(
            settings,
            text,
            settings.timezone,
            now_utc,
            fallback_start_utc=fallback_start,
        )
    except Exception as exc:
        logger.exception("Jev parse failed: %s", exc)
        if fast_result is not None:
            spec = parsed_reminder_to_spec(fast_result, ParseSource.FAST)
            return PipelineResult(spec=_apply_confidence_gate(spec, settings))
        return PipelineResult(
            error="Couldn't interpret that schedule. Try simpler wording.",
        )

    errors = validate_schedule_spec(spec, now_utc)
    if errors:
        spec.review = ReviewAction.CLARIFY
        spec.review_reason = "; ".join(errors)

    spec = _apply_confidence_gate(spec, settings)
    options = None
    if spec.review == ReviewAction.CLARIFY:
        options = ["One-time only", "Every day", "Every N days"]
    return PipelineResult(spec=spec, clarify_options=options)
