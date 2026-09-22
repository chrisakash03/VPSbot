from __future__ import annotations

import re

from aiogram import Bot
from aiogram.types import Message

_COMMAND_PREFIX = re.compile(r"^/\w+(@\w+)?\s*", re.IGNORECASE)


def extract_command_args(text: str, command: str) -> str:
    """Strip /command or /command@BotUsername prefix."""
    pattern = re.compile(rf"^/{command}(@\w+)?\s*", re.IGNORECASE)
    return pattern.sub("", text).strip()


def extract_text_if_mentioned(message: Message, bot_username: str) -> str | None:
    if not message.text or not message.entities:
        return None
    username = bot_username.lower().lstrip("@")
    mentioned = False
    for ent in message.entities:
        if ent.type != "mention":
            continue
        fragment = message.text[ent.offset : ent.offset + ent.length]
        if fragment.lower().lstrip("@") == username:
            mentioned = True
            break
    if not mentioned:
        return None
    body = message.text
    for ent in sorted(message.entities, key=lambda e: e.offset, reverse=True):
        if ent.type == "mention":
            fragment = message.text[ent.offset : ent.offset + ent.length]
            if fragment.lower().lstrip("@") == username:
                body = body[: ent.offset] + body[ent.offset + ent.length :]
    body = _COMMAND_PREFIX.sub("", body.strip())
    return re.sub(r"\s+", " ", body).strip() or None


def extract_reply_to_bot_text(message: Message, bot_id: int) -> str | None:
    if not message.text or not message.reply_to_message:
        return None
    reply_user = message.reply_to_message.from_user
    if not reply_user or reply_user.id != bot_id:
        return None
    return message.text.strip() or None


async def get_bot_username(bot: Bot) -> str:
    me = await bot.me()
    return me.username or ""
