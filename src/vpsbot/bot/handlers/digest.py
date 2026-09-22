from __future__ import annotations

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from vpsbot.bot.deps import BotContext
from vpsbot.rss.digest_group import set_digest_group_enabled

router = Router(name="digest")


@router.message(Command("digest"))
async def cmd_digest(message: Message, command: CommandObject, ctx: BotContext) -> None:
    arg = (command.args or "").strip().lower()
    if arg not in {"on", "off"}:
        await message.answer(
            "Usage: /digest on — enable daily digest in this group\n/digest off — disable"
        )
        return

    if message.chat.type == ChatType.PRIVATE:
        await message.answer("Digest is only enabled in the configured group.")
        return

    group_id = ctx.settings.digest_group_chat_id
    if group_id is None:
        await message.answer(
            "Digest group is not configured. Set DIGEST_GROUP_CHAT_ID in .env "
            "(use /chatid in the target group while admin)."
        )
        return

    if message.chat.id != group_id:
        await message.answer("Digest can only be toggled in the configured digest group.")
        return

    if message.from_user.id != ctx.settings.telegram_admin_user_id:
        await message.answer("Admin only.")
        return

    enabled = arg == "on"
    async with ctx.session_factory() as session:
        await set_digest_group_enabled(
            session,
            group_chat_id=group_id,
            enabled=enabled,
            updated_by=message.from_user.id,
        )
    if enabled:
        await message.answer("Daily RSS digest enabled for this group.")
    else:
        await message.answer("Daily RSS digest disabled for this group.")
