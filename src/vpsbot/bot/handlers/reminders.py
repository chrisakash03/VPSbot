from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from vpsbot.bot.delivery import resolve_notify_chat_id, strip_pm_modifier
from vpsbot.bot.deps import BotContext
from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.formatting import format_schedule_preview, format_schedule_summary
from vpsbot.reminders.pending import delete_pending, get_pending, save_pending
from vpsbot.reminders.pipeline import parse_reminder_pipeline
from vpsbot.reminders.schedule_spec import ReviewAction
from vpsbot.reminders.service import (
    cancel_reminder,
    create_reminder_from_spec,
    get_reminder,
    list_active_reminders,
)
from vpsbot.utils.timezone import format_local

router = Router(name="reminders")


async def _persist_and_schedule(
    message: Message,
    ctx: BotContext,
    spec,
    *,
    notify_chat_id: int,
    deliver_via_pm: bool,
) -> None:
    async with ctx.session_factory() as session:
        reminder = await create_reminder_from_spec(
            session,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            notify_chat_id=notify_chat_id,
            spec=spec,
        )
    await ctx.scheduler.schedule_reminder(reminder)
    await message.answer(
        format_schedule_summary(
            spec,
            ctx.settings.timezone,
            deliver_via_pm=deliver_via_pm,
        )
    )


async def process_reminder_request(
    message: Message,
    ctx: BotContext,
    raw_text: str,
    *,
    deliver_via_pm: bool = False,
) -> None:
    if not message.from_user:
        return
    text, pm_from_text = strip_pm_modifier(raw_text)
    deliver_via_pm = deliver_via_pm or pm_from_text
    if not text:
        await message.answer(
            "Usage: /r remind me to … tomorrow at 5pm (add /pm to get a DM instead)"
        )
        return

    notify_chat_id = resolve_notify_chat_id(message, deliver_via_pm)

    result = await parse_reminder_pipeline(text, ctx.settings)
    if result.error:
        await message.answer(result.error)
        return
    spec = result.spec
    if spec is None:
        await message.answer("Could not parse reminder.")
        return

    if spec.review == ReviewAction.AUTO:
        await _persist_and_schedule(
            message,
            ctx,
            spec,
            notify_chat_id=notify_chat_id,
            deliver_via_pm=deliver_via_pm,
        )
        return

    async with ctx.session_factory() as session:
        pending = await save_pending(
            session,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            notify_chat_id=notify_chat_id,
            spec=spec,
        )

    summary = format_schedule_summary(
        spec,
        ctx.settings.timezone,
        deliver_via_pm=deliver_via_pm,
    )
    reason = spec.review_reason or "Please confirm."

    if spec.review == ReviewAction.CONFIRM:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Yes, schedule",
                        callback_data=f"reminder:confirm:{pending.id}",
                    ),
                    InlineKeyboardButton(
                        text="Cancel",
                        callback_data=f"reminder:cancel:{pending.id}",
                    ),
                ]
            ]
        )
        await message.answer(f"{summary}\n\n{reason}", reply_markup=keyboard)
        return

    buttons = []
    if result.clarify_options:
        for label in result.clarify_options[:3]:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=label,
                        callback_data=f"reminder:clarify:{pending.id}",
                    )
                ]
            )
    buttons.append(
        [
            InlineKeyboardButton(
                text="Cancel",
                callback_data=f"reminder:cancel:{pending.id}",
            )
        ]
    )
    clarify_body = f"I wasn't sure how to read that.\n{reason}"
    if spec.review_reason and "past" not in (spec.review_reason or "").lower():
        clarify_body += f"\n\nBest guess: {format_schedule_preview(spec, ctx.settings.timezone)}"
    await message.answer(
        clarify_body,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode=None,
    )


@router.message(Command("r"))
async def cmd_reminder(message: Message, command: CommandObject, ctx: BotContext) -> None:
    text = (command.args or "").strip()
    await process_reminder_request(message, ctx, text)


@router.callback_query(F.data.startswith("reminder:confirm:"))
async def on_reminder_confirm(query: CallbackQuery, ctx: BotContext) -> None:
    if not query.data or not query.from_user or not query.message:
        return
    pending_id = int(query.data.split(":")[2])
    async with ctx.session_factory() as session:
        pending_data = await get_pending(session, pending_id, query.from_user.id)
        if not pending_data:
            await query.answer("Expired or not found.", show_alert=True)
            return
        spec, notify_chat_id = pending_data
        spec.review = ReviewAction.AUTO
        deliver_via_pm = notify_chat_id == query.from_user.id
        reminder = await create_reminder_from_spec(
            session,
            user_id=query.from_user.id,
            chat_id=query.message.chat.id,
            notify_chat_id=notify_chat_id,
            spec=spec,
        )
        await delete_pending(session, pending_id, query.from_user.id)
    await ctx.scheduler.schedule_reminder(reminder)
    await query.answer("Scheduled.")
    await query.message.edit_text(
        format_schedule_summary(
            spec,
            ctx.settings.timezone,
            deliver_via_pm=deliver_via_pm,
        )
    )


@router.callback_query(F.data.startswith("reminder:cancel:"))
async def on_reminder_cancel_pending(query: CallbackQuery, ctx: BotContext) -> None:
    if not query.data or not query.from_user:
        return
    pending_id = int(query.data.split(":")[2])
    async with ctx.session_factory() as session:
        await delete_pending(session, pending_id, query.from_user.id)
    await query.answer("Cancelled.")
    if query.message:
        await query.message.edit_text("Reminder not scheduled.")


@router.callback_query(F.data.startswith("reminder:clarify:"))
async def on_reminder_clarify(query: CallbackQuery, ctx: BotContext) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(
            "Try rephrasing with one clear time, e.g.\n"
            "/r every 2 days at 8pm for 2 weeks — submit the report"
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
        extra = ""
        if rem.recurrence_rule and rem.recurrence != RecurrenceKind.NONE.value:
            import json
            from datetime import datetime

            rule = json.loads(rem.recurrence_rule)
            if rule.get("remaining_occurrences") is not None:
                extra = f" [{rule['remaining_occurrences']} left]"
            elif rule.get("ends_at"):
                extra = f" [until {format_local(datetime.fromisoformat(rule['ends_at']), ctx.settings.timezone)}]"
        dm = ""
        if (
            rem.notify_chat_id == message.from_user.id
            and rem.chat_id != rem.notify_chat_id
        ):
            dm = " [DM]"
        lines.append(f"#{rem.id}: {rem.message} — {when}{recur}{extra}{dm}")
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
