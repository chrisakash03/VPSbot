from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vpsbot.db.models import Feed, RssQueueItem
from vpsbot.rss.diff import diff_new_entries
from vpsbot.rss.feed import fetch_feed_entries

logger = logging.getLogger(__name__)


async def seed_feeds_from_yaml(session: AsyncSession, yaml_path: Path) -> None:
    if not yaml_path.exists():
        return
    data = yaml.safe_load(yaml_path.read_text()) or {}
    urls = data.get("feeds") or []
    for url in urls:
        if not url:
            continue
        existing = await session.execute(select(Feed).where(Feed.url == url))
        if existing.scalar_one_or_none():
            continue
        session.add(Feed(url=url))
    await session.commit()


async def poll_all_feeds(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        result = await session.execute(select(Feed))
        feeds = list(result.scalars().all())

    for feed in feeds:
        try:
            title, entries = fetch_feed_entries(feed.url)
        except Exception as exc:
            logger.warning("Feed poll failed %s: %s", feed.url, exc)
            continue

        new_entries, new_last = diff_new_entries(entries, feed.last_seen_id)
        if not new_entries and title and not feed.title:
            async with session_factory() as session:
                db_feed = await session.get(Feed, feed.id)
                if db_feed:
                    db_feed.title = title
                    await session.commit()
            continue

        if not new_entries:
            continue

        now = datetime.now(ZoneInfo("UTC"))
        async with session_factory() as session:
            db_feed = await session.get(Feed, feed.id)
            if not db_feed:
                continue
            if title:
                db_feed.title = title
            for entry in new_entries:
                session.add(
                    RssQueueItem(
                        feed_id=db_feed.id,
                        guid=entry.guid,
                        link=entry.link,
                        title=entry.title,
                        published_at=entry.published_at,
                        collected_at=now,
                        digested=False,
                    )
                )
            if new_last:
                db_feed.last_seen_id = new_last
            await session.commit()
        logger.info("Queued %s new items from %s", len(new_entries), feed.url)
