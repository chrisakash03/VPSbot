from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from vpsbot.config import Settings
from vpsbot.db.models import RssQueueItem
from vpsbot.llm.digest import DigestItem, summarize_digest
from vpsbot.rss.digest_group import any_digest_group_enabled

logger = logging.getLogger(__name__)


async def run_daily_digest(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    send_message: Callable[[int, str], Awaitable[None]],
) -> None:
    group_id = settings.digest_group_chat_id
    if group_id is None:
        logger.info("Digest skipped: DIGEST_GROUP_CHAT_ID not set")
        return

    async with session_factory() as session:
        if not await any_digest_group_enabled(session, group_id):
            logger.info("Digest skipped: disabled for group %s", group_id)
            return

        stmt = (
            select(RssQueueItem)
            .where(RssQueueItem.digested.is_(False))
            .options(selectinload(RssQueueItem.feed))
            .order_by(RssQueueItem.collected_at.asc())
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

    if not items:
        if settings.digest_send_empty:
            await send_message(group_id, "Nothing new in your feeds today.")
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

    await send_message(group_id, summary)

    async with session_factory() as session:
        for item in items:
            db_item = await session.get(RssQueueItem, item.id)
            if db_item:
                db_item.digested = True
        await session.commit()
    logger.info("Digest sent to group %s (%s items)", group_id, len(items))
