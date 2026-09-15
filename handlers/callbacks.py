import logging
from datetime import timedelta

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from models.reminder import ReminderType, ReminderStatus
from services import firebase_service, scheduler_service
from utils.timezones import now_in_tz

logger = logging.getLogger(__name__)
router = Router(name="callbacks")


@router.callback_query(F.data.startswith("done:"))
async def on_done(callback: CallbackQuery) -> None:
    reminder_id = callback.data.split(":", 1)[1]
    reminder = await firebase_service.get_reminder(reminder_id)
    if reminder is None:
        await callback.answer("Eslatma topilmadi.", show_alert=True)
        return

    if reminder.type == ReminderType.ONCE:
        # One-off reminder: "done" really does end its lifecycle.
        await firebase_service.update_reminder_status(reminder_id, ReminderStatus.COMPLETED)
        scheduler_service.remove_job(reminder_id)
        await callback.message.edit_text(f"✅ Bajarildi: {reminder.title}")
    else:
        # Recurring reminder: marking a single occurrence "done" must NOT
        # cancel the whole series (that would silently kill future daily/
        # weekly/monthly/yearly notifications, which is not what the user
        # wants). Just acknowledge this occurrence; the job stays scheduled.
        await callback.message.edit_text(f"✅ Bugungi bosqich bajarildi deb belgilandi: {reminder.title}")

    await callback.answer()


async def _snooze(callback: CallbackQuery, bot: Bot, minutes: int) -> None:
    reminder_id = callback.data.split(":", 1)[1]
    reminder = await firebase_service.get_reminder(reminder_id)
    if reminder is None:
        await callback.answer("Eslatma topilmadi.", show_alert=True)
        return

    if reminder.type != ReminderType.ONCE:
        await callback.answer("Kechiktirish faqat bir martalik eslatmalar uchun mavjud.", show_alert=True)
        return

    new_dt = now_in_tz(reminder.timezone) + timedelta(minutes=minutes)
    reminder.target_datetime = new_dt

    await firebase_service.update_reminder_target_datetime(reminder_id, new_dt)
    scheduler_service.schedule_reminder(bot, reminder)

    await callback.message.edit_text(
        f"⏰ Eslatma {minutes} daqiqaga kechiktirildi: {reminder.title}\n"
        f"Yangi vaqt: {new_dt.strftime('%d.%m.%Y %H:%M')}"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("snooze15:"))
async def on_snooze15(callback: CallbackQuery, bot: Bot) -> None:
    await _snooze(callback, bot, 15)


@router.callback_query(F.data.startswith("snooze60:"))
async def on_snooze60(callback: CallbackQuery, bot: Bot) -> None:
    await _snooze(callback, bot, 60)
