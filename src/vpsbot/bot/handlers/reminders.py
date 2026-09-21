from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from vpsbot.bot.deps import BotContext
from vpsbot.reminders.parsing import ParseError, parse_reminder_text
from vpsbot.reminders.service import cancel_reminder, create_reminder, get_reminder, list_active_reminders
from vpsbot.utils.timezone import format_local

router = Router(name="reminders")


@router.message(Command("r"))
async def cmd_reminder(message: Message, ctx: BotContext) -> None:
    text = (message.text or "").removeprefix("/r").strip()
    if not text:
        await message.answer("Usage: /r remind me to … tomorrow at 5pm")
        return
    try:
        parsed = parse_reminder_text(text, ctx.settings.timezone)
    except ParseError as exc:
        await message.answer(str(exc))
        return

    async with ctx.session_factory() as session:
        reminder = await create_reminder(
            session,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            message=parsed.message,
            fire_at_utc=parsed.fire_at_utc,
            recurrence=parsed.recurrence,
            recurrence_rule=parsed.recurrence_rule,
        )
    await ctx.scheduler.schedule_reminder(reminder)
    when = format_local(parsed.fire_at_utc, ctx.settings.timezone)
    await message.answer(
        f"Got it — I'll remind you to '{parsed.message}' on {when}."
    )


@router.message(Command("list"))
async def cmd_list(message: Message, ctx: BotContext) -> None:
    async with ctx.session_factory() as session:
        reminders = await list_active_reminders(session, message.from_user.id)
    if not reminders:
        await message.answer("You have no upcoming reminders.")
        return
    lines = []
    for rem in reminders:
        when = format_local(rem.next_fire_at, ctx.settings.timezone)
        recur = f" ({rem.recurrence})" if rem.recurrence != "none" else ""
        lines.append(f"#{rem.id}: {rem.message} — {when}{recur}")
    await message.answer("\n".join(lines))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, ctx: BotContext) -> None:
    async with ctx.session_factory() as session:
        reminders = await list_active_reminders(session, message.from_user.id)
    if not reminders:
        await message.answer("You have no reminders to cancel.")
        return
    buttons = [
        [
            InlineKeyboardButton(
                text=f"#{r.id} {r.message[:40]}",
                callback_data=f"cancel:{r.id}",
            )
        ]
        for r in reminders[:20]
    ]
    await message.answer(
        "Pick a reminder to cancel:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("cancel:"))
async def on_cancel_pick(query: CallbackQuery, ctx: BotContext) -> None:
    if not query.data or not query.from_user:
        return
    reminder_id = int(query.data.split(":", 1)[1])
    async with ctx.session_factory() as session:
        reminder = await get_reminder(session, reminder_id, query.from_user.id)
        if not reminder:
            await query.answer("Reminder not found.", show_alert=True)
            return
        await cancel_reminder(session, reminder)
    await ctx.scheduler.unschedule_reminder(reminder_id)
    await query.answer("Cancelled.")
    if query.message:
        await query.message.edit_text(f"Cancelled reminder #{reminder_id}.")
