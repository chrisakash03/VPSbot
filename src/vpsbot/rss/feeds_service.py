from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vpsbot.db.models import Feed


async def list_feeds(session: AsyncSession) -> list[Feed]:
    result = await session.execute(select(Feed).order_by(Feed.id.asc()))
    return list(result.scalars().all())


async def add_feed(session: AsyncSession, url: str) -> Feed:
    existing = await session.execute(select(Feed).where(Feed.url == url))
    found = existing.scalar_one_or_none()
    if found:
        return found
    feed = Feed(url=url)
    session.add(feed)
    await session.commit()
    await session.refresh(feed)
    return feed


async def remove_feed(session: AsyncSession, url_or_id: str) -> bool:
    feed: Feed | None = None
    if url_or_id.isdigit():
        feed = await session.get(Feed, int(url_or_id))
    if feed is None:
        result = await session.execute(select(Feed).where(Feed.url == url_or_id))
        feed = result.scalar_one_or_none()
    if feed is None:
        return False
    await session.delete(feed)
    await session.commit()
    return True
