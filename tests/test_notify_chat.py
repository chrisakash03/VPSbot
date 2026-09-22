from unittest.mock import MagicMock

from vpsbot.bot.delivery import resolve_notify_chat_id


def test_resolve_notify_chat_id_group():
    message = MagicMock()
    message.chat.id = -100123
    message.from_user.id = 42
    assert resolve_notify_chat_id(message, False) == -100123


def test_resolve_notify_chat_id_pm():
    message = MagicMock()
    message.chat.id = -100123
    message.from_user.id = 42
    assert resolve_notify_chat_id(message, True) == 42
