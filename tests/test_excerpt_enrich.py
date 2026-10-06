from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vpsbot.db.migrate import run_sqlite_migrations
from vpsbot.db.models import ExcerptStatus, Feed, RssQueueItem
from vpsbot.db.session import init_db
from vpsbot.llm.digest import DigestItem, _build_prompt
from vpsbot.rss.enrich import enrich_pending, summary_is_enough, upcoming_digest
from vpsbot.rss.feed import clip_plain_text, entry_summary
from vpsbot.rss.memory import HostMemory, memory_is_hot, parse_meminfo
from vpsbot.scheduler.service import enrich_clock

UTC = ZoneInfo("UTC")


def test_entry_summary_strips_html_and_clips():
    raw = {"summary": "<p>Hello&nbsp;<b>world</b></p>" + (" word" * 2000)}
    text = entry_summary(raw)
    assert "<" not in text
    assert "Hello" in text
    assert len(text) <= 2000
    assert clip_plain_text("  a   b  ", 10) == "a b"


def test_entry_summary_falls_back_to_content():
    raw = {"content": [{"value": "<div>Full article body.</div>"}]}
    assert entry_summary(raw) == "Full article body."


def test_summary_is_enough_rejects_title_repeat_and_short_blurbs():
    assert summary_is_enough("x" * 500, "Headline")
    assert not summary_is_enough("too short", "Headline")
    assert not summary_is_enough("Headline", "headline")


def test_enrich_clock_wraps_past_midnight():
    assert enrich_clock("08:00") == (7, 30)
    assert enrich_clock("00:10") == (23, 40)


def test_upcoming_digest_same_morning_and_after_midnight_wrap():
    morning = datetime(2026, 10, 4, 7, 30, tzinfo=UTC)
    assert upcoming_digest(morning, "08:00") == datetime(2026, 10, 4, 8, 0, tzinfo=UTC)
    late = datetime(2026, 10, 4, 23, 40, tzinfo=UTC)
    assert upcoming_digest(late, "00:10") == datetime(2026, 10, 5, 0, 10, tzinfo=UTC)


def test_memory_hot_at_950mb_used_and_low_available():
    cool = parse_meminfo("MemTotal: 1048576 kB\nMemAvailable: 204800 kB\n")
    assert cool is not None
    assert memory_is_hot(cool) is False
    hot = parse_meminfo("MemTotal: 1048576 kB\nMemAvailable: 75776 kB\n")
    assert hot is not None
    assert hot.used_bytes >= 950 * 1024 * 1024
    assert memory_is_hot(hot) is True
    low = HostMemory(total_bytes=2 * 1024 * 1024 * 1024, available_bytes=63 * 1024 * 1024)
    assert memory_is_hot(low) is True


def test_rss_queue_migration_adds_excerpt_columns():
    from sqlalchemy import create_engine

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE rss_queue (
                    id INTEGER PRIMARY KEY,
                    feed_id INTEGER,
                    guid VARCHAR(512),
                    link VARCHAR(2048),
                    title VARCHAR(1024),
                    published_at DATETIME,
                    collected_at DATETIME,
                    digested BOOLEAN
                )
                """
            )
        )
        run_sqlite_migrations(conn)
        cols = {c["name"] for c in inspect(conn).get_columns("rss_queue")}
    assert {"summary", "excerpt", "excerpt_status"} <= cols


def test_prompt_includes_excerpt():
    prompt = _build_prompt(
        [DigestItem(feed_title="OpenAI", title="Sites", link="https://openai.com/a", excerpt="Sites builds pages.")],
        digest_date="04 October 2026",
    )
    assert "Excerpt: Sites builds pages." in prompt
    empty = _build_prompt(
        [DigestItem(feed_title="OpenAI", title="Sites", link="https://openai.com/a")],
        digest_date="04 October 2026",
    )
    assert "Excerpt: (none)" in empty


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _queue(session_factory, items: list[tuple[str, str, str | None]]):
    now = datetime(2026, 10, 4, 7, 0, tzinfo=UTC)
    async with session_factory() as session:
        feed = Feed(url="https://example.com/rss", title="Example")
        session.add(feed)
        await session.flush()
        for index, (link, title, summary) in enumerate(items):
            session.add(
                RssQueueItem(
                    feed_id=feed.id,
                    guid=f"g{index}",
                    link=link,
                    title=title,
                    summary=summary,
                    collected_at=now,
                    digested=False,
                )
            )
        await session.commit()


@pytest.mark.asyncio
async def test_enrich_uses_rss_body_without_fetch():
    engine, session_factory = await _factory()
    body = "OpenAI described Sites as a way to publish a page from a chat. " * 8
    await _queue(session_factory, [("https://example.com/a", "Sites", body)])
    fetched: list[str] = []

    async def fetch(url: str) -> str:
        fetched.append(url)
        return "page"

    deadline = datetime(2026, 10, 4, 8, 0, tzinfo=UTC)
    await enrich_pending(
        session_factory,
        deadline=deadline,
        tz_name="UTC",
        fetch=fetch,
        memory_hot=lambda: False,
        now=lambda: datetime(2026, 10, 4, 7, 30, tzinfo=UTC),
    )
    assert fetched == []
    async with session_factory() as session:
        item = (await session.execute(select(RssQueueItem))).scalar_one()
        assert item.excerpt_status == ExcerptStatus.READY.value
        assert item.excerpt == body
    await engine.dispose()


@pytest.mark.asyncio
async def test_enrich_fetches_one_at_a_time_and_commits():
    engine, session_factory = await _factory()
    await _queue(
        session_factory,
        [
            ("https://example.com/1", "One", "short"),
            ("https://example.com/2", "Two", "short"),
        ],
    )
    seen: list[list[str]] = []

    async def fetch(url: str) -> str:
        async with session_factory() as session:
            rows = (
                await session.execute(select(RssQueueItem).order_by(RssQueueItem.id))
            ).scalars().all()
            seen.append([row.excerpt_status for row in rows])
        return ("extracted " + url) * 20

    await enrich_pending(
        session_factory,
        deadline=datetime(2026, 10, 4, 8, 0, tzinfo=UTC),
        tz_name="UTC",
        fetch=fetch,
        memory_hot=lambda: False,
        now=lambda: datetime(2026, 10, 4, 7, 31, tzinfo=UTC),
    )
    assert seen[0] == [ExcerptStatus.PENDING.value, ExcerptStatus.PENDING.value]
    assert seen[1][0] == ExcerptStatus.READY.value
    await engine.dispose()


@pytest.mark.asyncio
async def test_enrich_stops_when_memory_stays_hot():
    engine, session_factory = await _factory()
    await _queue(session_factory, [("https://example.com/1", "One", "short")])
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    async def fetch(url: str) -> str:
        raise AssertionError("should not fetch")

    await enrich_pending(
        session_factory,
        deadline=datetime(2026, 10, 4, 8, 0, tzinfo=UTC),
        tz_name="UTC",
        fetch=fetch,
        memory_hot=lambda: True,
        sleep=sleep,
        now=lambda: datetime(2026, 10, 4, 7, 31, tzinfo=UTC),
    )
    assert sleeps == [15, 15, 15]
    async with session_factory() as session:
        item = (await session.execute(select(RssQueueItem))).scalar_one()
        assert item.excerpt_status == ExcerptStatus.PENDING.value
    await engine.dispose()


@pytest.mark.asyncio
async def test_enrich_stops_at_digest_deadline():
    engine, session_factory = await _factory()
    await _queue(session_factory, [("https://example.com/1", "One", "short")])

    async def fetch(url: str) -> str:
        raise AssertionError("should not fetch")

    deadline = datetime(2026, 10, 4, 8, 0, tzinfo=UTC)
    await enrich_pending(
        session_factory,
        deadline=deadline,
        tz_name="UTC",
        fetch=fetch,
        memory_hot=lambda: False,
        now=lambda: deadline,
    )
    async with session_factory() as session:
        item = (await session.execute(select(RssQueueItem))).scalar_one()
        assert item.excerpt_status == ExcerptStatus.PENDING.value
    await engine.dispose()
