from __future__ import annotations

import logging

import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from models.reminder import Reminder, ReminderType
from keyboards.inline import notification_keyboard
from services import firebase_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def _build_trigger(reminder: Reminder):
    tz = pytz.timezone(reminder.timezone)
    dt = reminder.target_datetime
    hour, minute = dt.hour, dt.minute

    if reminder.type == ReminderType.ONCE:
        return DateTrigger(run_date=dt, timezone=tz)
    if reminder.type == ReminderType.DAILY:
        return CronTrigger(hour=hour, minute=minute, timezone=tz)
    if reminder.type == ReminderType.WEEKLY:
        from models.reminder import WEEKDAY_TO_CRON
        cron_day = WEEKDAY_TO_CRON[reminder.day_of_week.lower()]
        return CronTrigger(day_of_week=cron_day, hour=hour, minute=minute, timezone=tz)
    if reminder.type == ReminderType.MONTHLY:
        return CronTrigger(day=reminder.day_of_month, hour=hour, minute=minute, timezone=tz)
    if reminder.type == ReminderType.YEARLY:
        return CronTrigger(month=dt.month, day=dt.day, hour=hour, minute=minute, timezone=tz)

    raise ValueError(f"Unsupported reminder type: {reminder.type}")


def schedule_reminder(bot: Bot, reminder: Reminder) -> None:
    trigger = _build_trigger(reminder)
    scheduler.add_job(
        _fire_notification,
        trigger=trigger,
        args=[bot, reminder.reminder_id],
        id=reminder.reminder_id,
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Scheduled reminder %s (%s)", reminder.reminder_id, reminder.type.value)


def remove_job(reminder_id: str) -> None:
    if scheduler.get_job(reminder_id):
        scheduler.remove_job(reminder_id)
        logger.info("Removed job %s", reminder_id)


async def _fire_notification(bot: Bot, reminder_id: str) -> None:
    reminder = await firebase_service.get_reminder(reminder_id)
    if reminder is None or reminder.status.value != "active":
        remove_job(reminder_id)
        return

    creator_info = f"\n👤 <i>Yaratdi: {reminder.creator_name}</i>" if reminder.creator_name else ""
    text = f"⏰ <b>Eslatma:</b> {reminder.title}{creator_info}"
    markup = notification_keyboard(reminder.reminder_id, reminder.type.value)

    try:
        if reminder.file_id and reminder.file_type == "photo":
            await bot.send_photo(
                chat_id=reminder.user_id,
                photo=reminder.file_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        elif reminder.file_id and reminder.file_type == "document":
            await bot.send_document(
                chat_id=reminder.user_id,
                document=reminder.file_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        else:
            await bot.send_message(
                chat_id=reminder.user_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
    except Exception:
        logger.exception("Failed to send notification for reminder %s", reminder_id)


async def reschedule_all(bot: Bot) -> int:
    """Called on startup. Rebuilds every active reminder's job."""
    reminders = await firebase_service.get_all_active_reminders()
    count = 0
    for reminder in reminders:
        try:
            schedule_reminder(bot, reminder)
            count += 1
        except Exception:
            logger.exception("Failed to reschedule reminder %s", reminder.reminder_id)
    logger.info("Rescheduled %d active reminders", count)
    return count
