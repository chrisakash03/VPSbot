from __future__ import annotations

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from vpsbot.bot.deps import BotContext
from vpsbot.rss.feeds_service import add_feed, list_feeds, remove_feed

router = Router(name="feeds")


def _is_admin(message: Message, ctx: BotContext) -> bool:
    return message.from_user is not None and message.from_user.id == ctx.settings.telegram_admin_user_id


def _require_dm(message: Message) -> bool:
    return message.chat.type == ChatType.PRIVATE


@router.message(Command("addfeed"))
async def cmd_addfeed(message: Message, ctx: BotContext) -> None:
    if not _require_dm(message):
        await message.answer("Feed management is only available in a private chat with me.")
        return
    if not _is_admin(message, ctx):
        await message.answer("Admin only.")
        return
    url = (message.text or "").removeprefix("/addfeed").strip()
    if not url:
        await message.answer("Usage: /addfeed https://example.com/rss")
        return
    async with ctx.session_factory() as session:
        feed = await add_feed(session, url)
    await message.answer(f"Feed added (#{feed.id}): {feed.url}")


@router.message(Command("removefeed"))
async def cmd_removefeed(message: Message, ctx: BotContext) -> None:
    if not _require_dm(message):
        await message.answer("Feed management is only available in a private chat with me.")
        return
    if not _is_admin(message, ctx):
        await message.answer("Admin only.")
        return
    arg = (message.text or "").removeprefix("/removefeed").strip()
    if not arg:
        await message.answer("Usage: /removefeed <url or id>")
        return
    async with ctx.session_factory() as session:
        ok = await remove_feed(session, arg)
    if ok:
        await message.answer("Feed removed.")
    else:
        await message.answer("Feed not found.")


@router.message(Command("listfeeds"))
async def cmd_listfeeds(message: Message, ctx: BotContext) -> None:
    if not _require_dm(message):
        await message.answer("Feed management is only available in a private chat with me.")
        return
    if not _is_admin(message, ctx):
        await message.answer("Admin only.")
        return
    async with ctx.session_factory() as session:
        feeds = await list_feeds(session)
    if not feeds:
        await message.answer("No feeds configured.")
        return
    lines = [f"#{f.id}: {f.title or '(no title)'} — {f.url}" for f in feeds]
    await message.answer("\n".join(lines))
