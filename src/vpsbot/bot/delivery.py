from __future__ import annotations

import re

from aiogram.types import Message

_PM_TOKEN = re.compile(r"(?:^|\s)/pm(?:\s|$)", re.IGNORECASE)


def strip_pm_modifier(text: str) -> tuple[str, bool]:
    """Remove /pm token and return cleaned text + whether DM delivery was requested."""
    if not _PM_TOKEN.search(text):
        return text.strip(), False
    cleaned = _PM_TOKEN.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip(), True


def resolve_notify_chat_id(message: Message, deliver_via_pm: bool) -> int:
    if deliver_via_pm:
        if message.from_user is None:
            raise ValueError("Missing from_user for DM delivery")
        return message.from_user.id
    return message.chat.id
