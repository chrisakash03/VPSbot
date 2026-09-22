from unittest.mock import MagicMock

from aiogram.types import MessageEntity

from vpsbot.bot.delivery import strip_pm_modifier
from vpsbot.bot.telegram_text import extract_command_args, extract_text_if_mentioned


def test_strip_pm_modifier():
    text, pm = strip_pm_modifier("tomorrow 5pm /pm standup")
    assert pm is True
    assert "/pm" not in text
    assert "standup" in text


def test_strip_pm_no_modifier():
    text, pm = strip_pm_modifier("tomorrow 5pm")
    assert pm is False


def test_extract_command_args_with_bot_name():
    assert extract_command_args("/r@MyBot remind me", "r") == "remind me"


def test_extract_mention_text():
    message = MagicMock()
    message.text = "@mybot remind me in 5 minutes"
    message.entities = [
        MessageEntity(type="mention", offset=0, length=6),
    ]
    assert extract_text_if_mentioned(message, "mybot") == "remind me in 5 minutes"
