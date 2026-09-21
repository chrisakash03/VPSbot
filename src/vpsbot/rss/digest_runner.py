from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from vpsbot.config import Settings
from vpsbot.db.models import DigestSubscriber, RssQueueItem
from vpsbot.llm.digest import DigestItem, summarize_digest

logger = logging.getLogger(__name__)


async def run_daily_digest(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    send_message: Callable[[int, str], Awaitable[None]],
) -> None:
    async with session_factory() as session:
        stmt = (
            select(RssQueueItem)
            .where(RssQueueItem.digested.is_(False))
            .options(selectinload(RssQueueItem.feed))
            .order_by(RssQueueItem.collected_at.asc())
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        sub_result = await session.execute(
            select(DigestSubscriber).where(DigestSubscriber.enabled.is_(True))
        )
        subscribers = list(sub_result.scalars().all())

    if not subscribers:
        logger.info("Digest skipped: no subscribers")
        return

    if not items:
        if settings.digest_send_empty:
            for sub in subscribers:
                await send_message(sub.chat_id, "Nothing new in your feeds today.")
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
    try:
        summary = summarize_digest(digest_items, api_key=settings.openai_api_key)
    except Exception as exc:
        logger.exception("Digest LLM failed: %s", exc)
        summary = "Daily digest failed to generate. Check bot logs."

    for sub in subscribers:
        await send_message(sub.chat_id, summary)

    async with session_factory() as session:
        for item in items:
            db_item = await session.get(RssQueueItem, item.id)
            if db_item:
                db_item.digested = True
        await session.commit()
    logger.info("Digest sent to %s subscribers (%s items)", len(subscribers), len(items))
