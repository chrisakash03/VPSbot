from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from vpsbot.bot.deps import BotContext
from vpsbot.db.models import DigestSubscriber

router = Router(name="digest")


@router.message(Command("digest"))
async def cmd_digest(message: Message, ctx: BotContext) -> None:
    arg = (message.text or "").removeprefix("/digest").strip().lower()
    if arg not in {"on", "off"}:
        await message.answer("Usage: /digest on — subscribe to daily digest\n/digest off — unsubscribe")
        return
    enabled = arg == "on"
    async with ctx.session_factory() as session:
        result = await session.execute(
            select(DigestSubscriber).where(DigestSubscriber.user_id == message.from_user.id)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            sub = DigestSubscriber(
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                enabled=enabled,
            )
            session.add(sub)
        else:
            sub.enabled = enabled
            sub.chat_id = message.chat.id
        await session.commit()
    if enabled:
        await message.answer("You'll receive the daily RSS digest.")
    else:
        await message.answer("Daily digest disabled.")
