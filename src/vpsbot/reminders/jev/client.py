from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from vpsbot.config import Settings
from vpsbot.reminders.jev.assemble import assemble_from_answers
from vpsbot.reminders.jev.questions import reminder_questions
from vpsbot.reminders.schedule_spec import ScheduleSpec

logger = logging.getLogger(__name__)


def build_jev_state(user_text: str, tz_name: str, now_utc: datetime) -> dict[str, str]:
    tz = ZoneInfo(tz_name)
    now_local = now_utc.astimezone(tz)
    return {
        "user_text": user_text,
        "timezone": tz_name,
        "now_local_iso": now_local.isoformat(),
        "now_utc_iso": now_utc.isoformat(),
        "weekday_local": now_local.strftime("%A"),
    }


async def parse_with_jev(
    settings: Settings,
    user_text: str,
    tz_name: str,
    now_utc: datetime,
    fallback_start_utc: datetime | None = None,
) -> ScheduleSpec:
    if not settings.jev_enabled or not settings.typesafe_api_key:
        raise RuntimeError("Jev is not configured")

    try:
        from typesafe_sdk import AsyncTypeSafeClient
    except ImportError as exc:
        raise RuntimeError("typesafe-sdk is not installed") from exc

    state = build_jev_state(user_text, tz_name, now_utc)
    client = AsyncTypeSafeClient(
        api_key=settings.typesafe_api_key,
        timeout=settings.jev_timeout_seconds,
    )
    response = await client.system_one(
        state=state,
        questions=reminder_questions(),
        model=settings.jev_model,
    )

    answers: dict[str, Any] = response.answers
    spec = assemble_from_answers(
        answers,
        user_text=user_text,
        tz_name=tz_name,
        now_utc=now_utc,
        fallback_start_utc=fallback_start_utc,
    )
    logger.info(
        "Jev parse confidence=%.2f review=%s recurrence=%s",
        spec.confidence or 0,
        spec.review.value,
        spec.recurrence.value,
    )
    return spec
