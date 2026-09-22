from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from vpsbot.config import Settings
from vpsbot.db.models import RssQueueItem
from vpsbot.llm.digest import DigestItem, summarize_digest
from vpsbot.rss.digest_group import any_digest_group_enabled

logger = logging.getLogger(__name__)


async def run_digest(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    send_message: Callable[[int, str], Awaitable[None]],
    destination_chat_id: int,
    *,
    require_group_enabled: int | None = None,
    notify_when_empty: bool | None = None,
) -> None:
    if require_group_enabled is not None:
        async with session_factory() as session:
            if not await any_digest_group_enabled(session, require_group_enabled):
                logger.info(
                    "Digest skipped: disabled for group %s", require_group_enabled
                )
                return

    async with session_factory() as session:
        stmt = (
            select(RssQueueItem)
            .where(RssQueueItem.digested.is_(False))
            .options(selectinload(RssQueueItem.feed))
            .order_by(RssQueueItem.collected_at.asc())
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

    if not items:
        send_empty = (
            notify_when_empty
            if notify_when_empty is not None
            else settings.digest_send_empty
        )
        if send_empty:
            await send_message(destination_chat_id, "Nothing new in your feeds today.")
        else:
            logger.info("Digest skipped: no new queue items")
        return

    digest_items = [
        DigestItem(
            feed_title=item.feed.title or item.feed.url,
            title=item.title,
            link=item.link,
        )
        for item in items
    ]
    digest_date = datetime.now(ZoneInfo(settings.timezone)).strftime("%d %B %Y")
    try:
        summary = summarize_digest(
            digest_items,
            api_key=settings.openai_api_key,
            digest_date=digest_date,
        )
    except Exception as exc:
        logger.exception("Digest LLM failed: %s", exc)
        summary = "Daily digest failed to generate. Check bot logs."

    await send_message(destination_chat_id, summary)

    async with session_factory() as session:
        for item in items:
            db_item = await session.get(RssQueueItem, item.id)
            if db_item:
                db_item.digested = True
        await session.commit()
    logger.info(
        "Digest sent to chat %s (%s items)", destination_chat_id, len(items)
    )


async def run_daily_digest(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    send_message: Callable[[int, str], Awaitable[None]],
) -> None:
    group_id = settings.digest_group_chat_id
    if group_id is None:
        logger.info("Digest skipped: DIGEST_GROUP_CHAT_ID not set")
        return

    await run_digest(
        session_factory,
        settings,
        send_message,
        group_id,
        require_group_enabled=group_id,
    )
