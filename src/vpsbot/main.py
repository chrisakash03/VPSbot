from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from vpsbot.app_state import AppState, set_state
from vpsbot.bot.deps import BotContext
from vpsbot.bot.handlers import digest, feeds, groups, reminders, start
from vpsbot.bot.telegram_text import get_bot_username
from vpsbot.bot.middleware import ContextMiddleware
from vpsbot.config import load_settings
from vpsbot.db.session import create_engine_and_session, init_db
from vpsbot.reminders.cleanup import purge_stale_data
from vpsbot.reminders.startup import catch_up_overdue_reminders
from vpsbot.rss.poller import seed_feeds_from_yaml
from vpsbot.scheduler.service import BotScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def feeds_yaml_path() -> Path:
    custom = os.getenv("FEEDS_YAML_PATH")
    if custom:
        return Path(custom)
    return Path(__file__).resolve().parents[2] / "feeds.yaml"


async def main() -> None:
    settings = load_settings()
    engine, session_factory = create_engine_and_session(settings)
    await init_db(engine)

    async with session_factory() as session:
        await seed_feeds_from_yaml(session, feeds_yaml_path())

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.me()
    dp = Dispatcher()

    scheduler = BotScheduler(settings, session_factory)
    ctx = BotContext(settings=settings, session_factory=session_factory, scheduler=scheduler)
    set_state(
        AppState(
            settings=settings,
            session_factory=session_factory,
            scheduler=scheduler,
            bot=bot,
            bot_id=me.id,
            bot_username=me.username or await get_bot_username(bot),
        )
    )

    dp.message.middleware(ContextMiddleware(ctx))
    dp.callback_query.middleware(ContextMiddleware(ctx))
    dp.include_router(start.router)
    dp.include_router(reminders.router)
    dp.include_router(feeds.router)
    dp.include_router(digest.router)
    dp.include_router(groups.router)

    scheduler.start()
    await purge_stale_data(session_factory, settings)
    await catch_up_overdue_reminders(session_factory, bot, scheduler)
    await scheduler.reload_reminders_from_db()
    scheduler.schedule_rss_poll()
    scheduler.schedule_daily_digest()

    logger.info("Starting long polling")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "my_chat_member"],
        )
    finally:
        scheduler.shutdown()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
