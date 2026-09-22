from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated, Message

from vpsbot.app_state import get_state
from vpsbot.bot.handlers.reminders import process_reminder_request
from vpsbot.bot.telegram_text import extract_reply_to_bot_text, extract_text_if_mentioned
from vpsbot.bot.deps import BotContext

router = Router(name="groups")


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text)
async def on_group_text(message: Message, ctx: BotContext) -> None:
    if not message.text or message.text.startswith("/"):
        return
    state = get_state()
    bot_id = state.bot_id
    username = state.bot_username
    if not bot_id or not username:
        return

    body = extract_text_if_mentioned(message, username)
    if body is None:
        body = extract_reply_to_bot_text(message, bot_id)
    if body is None:
        return

    await process_reminder_request(message, ctx, body)


@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_bot_added(event: ChatMemberUpdated) -> None:
    if event.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return
    state = get_state()
    username = state.bot_username or "bot"
    await state.bot.send_message(
        event.chat.id,
        f"Hi — mention @{username} with a reminder, or use /r …\n"
        "Add /pm to get a private DM when it fires (you need /start in DM with me first).\n"
        "/list and /cancel are per-user.\n"
        "Daily RSS digest is only in the configured digest group.",
        parse_mode=None,
    )
