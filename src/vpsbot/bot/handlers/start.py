from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from vpsbot.bot.deps import BotContext

router = Router(name="start")


def help_text() -> str:
    """Markdown body. Each example is inline code so Telegram can copy it in one tap."""
    return (
        "Reminder syntax. Tap a line to copy it.\n\n"
        "One time:\n"
        "`/r remind me tomorrow at 5pm`\n\n"
        "DM when it fires:\n"
        "`/r remind me tomorrow at 5pm /pm`\n\n"
        "Several times the same day:\n"
        "`/r take meds at 8am, 3pm, 8pm`\n\n"
        "Several days. A time with no day is today, so 11pm is today:\n"
        "`/r do this 3pm, tomorrow 5pm, next wednesday 8pm, 11pm`\n\n"
        "Repeats:\n"
        "`/r every day at 9am`\n"
        "`/r every monday at 8pm`\n"
        "`/r every day at 9am for 3 times`\n"
        "`/r every 2 days at 8pm for 2 weeks`\n\n"
        "Other commands:\n"
        "`/list`\n"
        "`/cancel`"
    )


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hi! I'm VPSbot.\n\n"
        "• /help — copy-paste reminder syntax\n"
        "• /r … — set a reminder (add /pm for a DM when it fires)\n"
        "• /list — your upcoming reminders\n"
        "• /cancel — remove a reminder\n\n"
        "In groups: @mention me with a reminder, or /r@BotName …\n"
        "Digest: /digest on|off in the configured digest group (admin).\n"
        "Admins: /digestnow — run the digest now in this chat.\n\n"
        "Admins (DM only): /addfeed, /removefeed, /listfeeds",
        parse_mode=None,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(help_text(), parse_mode="Markdown")


@router.message(Command("chatid"))
async def cmd_chatid(message: Message, ctx: BotContext) -> None:
    if message.from_user is None or message.from_user.id != ctx.settings.telegram_admin_user_id:
        await message.answer("Admin only.")
        return
    await message.answer(f"Chat ID: {message.chat.id}", parse_mode=None)
