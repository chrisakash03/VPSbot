from __future__ import annotations

import gc
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vpsbot.db.models import ExcerptStatus, RssQueueItem
from vpsbot.rss.extract import fetch_article_excerpt, fetchable_url
from vpsbot.rss.memory import host_memory_hot

logger = logging.getLogger(__name__)

RSS_BODY_MIN_CHARS = 400
MEMORY_RECHECKS = 4
MEMORY_PAUSE_SECONDS = 15


def upcoming_digest(now_local: datetime, digest_time: str) -> datetime:
    hour_str, minute_str = digest_time.strip().split(":")
    candidate = now_local.replace(
        hour=int(hour_str),
        minute=int(minute_str),
        second=0,
        microsecond=0,
    )
    if candidate <= now_local:
        candidate += timedelta(days=1)
    return candidate


def summary_is_enough(summary: str | None, title: str) -> bool:
    text = (summary or "").strip()
    if len(text) < RSS_BODY_MIN_CHARS:
        return False
    return text.casefold() != title.strip().casefold()


async def enrich_pending(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    deadline: datetime,
    tz_name: str,
    fetch: Callable[[str], Awaitable[str | None]] = fetch_article_excerpt,
    memory_hot: Callable[[], bool] = host_memory_hot,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    now: Callable[[], datetime] | None = None,
) -> None:
    if sleep is None:
        import asyncio

        sleep = asyncio.sleep
    tz = ZoneInfo(tz_name)

    def clock() -> datetime:
        return datetime.now(tz)

    if now is None:
        now = clock

    async with session_factory() as session:
        result = await session.execute(
            select(RssQueueItem.id)
            .where(
                RssQueueItem.digested.is_(False),
                RssQueueItem.excerpt_status == ExcerptStatus.PENDING.value,
            )
            .order_by(RssQueueItem.collected_at.asc(), RssQueueItem.id.asc())
        )
        item_ids = list(result.scalars().all())

    for item_id in item_ids:
        if now() >= deadline:
            logger.info("Excerpt enrichment stopped: digest time reached")
            return

        async with session_factory() as session:
            item = await session.get(RssQueueItem, item_id)
            if item is None or item.digested or item.excerpt_status != ExcerptStatus.PENDING.value:
                continue
            if summary_is_enough(item.summary, item.title):
                item.excerpt = item.summary
                item.excerpt_status = ExcerptStatus.READY.value
                await session.commit()
                continue
            link = item.link
            needs_fetch = fetchable_url(link)

        if not needs_fetch:
            await _mark(session_factory, item_id, None, ExcerptStatus.FAILED)
            continue

        if not await _memory_allows(memory_hot, sleep):
            logger.warning("Excerpt enrichment stopped: host memory is high")
            return
        if now() >= deadline:
            logger.info("Excerpt enrichment stopped: digest time reached")
            return

        try:
            excerpt = await fetch(link)
        except Exception:
            logger.exception("Excerpt fetch failed for %s", link)
            excerpt = None
        status = ExcerptStatus.READY if excerpt else ExcerptStatus.FAILED
        await _mark(session_factory, item_id, excerpt, status)
        del excerpt
        gc.collect()


async def _memory_allows(
    memory_hot: Callable[[], bool],
    sleep: Callable[[float], Awaitable[None]],
) -> bool:
    for attempt in range(MEMORY_RECHECKS):
        if not memory_hot():
            return True
        if attempt == MEMORY_RECHECKS - 1:
            return False
        logger.warning("Host memory high; pausing before the next excerpt fetch")
        await sleep(MEMORY_PAUSE_SECONDS)
    return False


async def _mark(
    session_factory: async_sessionmaker[AsyncSession],
    item_id: int,
    excerpt: str | None,
    status: ExcerptStatus,
) -> None:
    async with session_factory() as session:
        item = await session.get(RssQueueItem, item_id)
        if item is None or item.excerpt_status != ExcerptStatus.PENDING.value:
            return
        item.excerpt = excerpt
        item.excerpt_status = status.value
        await session.commit()
