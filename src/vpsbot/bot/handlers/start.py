from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from vpsbot.bot.deps import BotContext

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hi! I'm VPSbot.\n\n"
        "• /r … — set a reminder (add /pm for a DM when it fires)\n"
        "• /list — your upcoming reminders\n"
        "• /cancel — remove a reminder\n\n"
        "In groups: @mention me with a reminder, or /r@BotName …\n"
        "Digest: /digest on|off in the configured digest group (admin).\n"
        "Admins: /digestnow — run the digest now in this chat.\n\n"
        "Admins (DM only): /addfeed, /removefeed, /listfeeds",
        parse_mode=None,
    )


@router.message(Command("chatid"))
async def cmd_chatid(message: Message, ctx: BotContext) -> None:
    if message.from_user is None or message.from_user.id != ctx.settings.telegram_admin_user_id:
        await message.answer("Admin only.")
        return
    await message.answer(f"Chat ID: {message.chat.id}", parse_mode=None)
