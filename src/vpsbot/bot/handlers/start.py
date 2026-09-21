from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hi! I'm VPSbot.\n\n"
        "• /r <text> — set a reminder\n"
        "• /list — upcoming reminders\n"
        "• /cancel — remove a reminder\n"
        "• /digest on|off — daily RSS summary\n\n"
        "Admins: /addfeed, /removefeed, /listfeeds"
    )
