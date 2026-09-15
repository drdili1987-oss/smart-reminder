import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from handlers.states import ReminderFlow
from keyboards.inline import confirm_reminder_keyboard, reminder_list_item_keyboard
from models.reminder import Reminder, ReminderType, ReminderStatus
from services import firebase_service, scheduler_service
from services.ai_parser import parse_reminder_text, parse_reminder_audio, AIParseError
from utils.timezones import now_in_tz, localize, ensure_weekly_consistency

logger = logging.getLogger(__name__)
router = Router(name="reminders")

TYPE_LABELS = {
    "once": "Bir martalik",
    "daily": "Har kuni",
    "weekly": "Har hafta",
    "monthly": "Har oy",
    "yearly": "Har yili",
}

INVALID_TEXT_REPLY = (
    "Kechirasiz, eslatma vaqti yoki mazmunini aniqlay olmadim. "
    "Masalan: 'Ertaga 10:00 da yig'ilish' deb yozing."
)


def _format_confirmation(reminder: Reminder) -> str:
    lines = [
        "📝 Quyidagi eslatmani tasdiqlaysizmi?",
        "",
        f"<b>Mazmuni:</b> {reminder.title}",
        f"<b>Turi:</b> {TYPE_LABELS.get(reminder.type.value, reminder.type.value)}",
        f"<b>Sana/vaqt:</b> {reminder.target_datetime.strftime('%d.%m.%Y %H:%M')}",
    ]
    if reminder.type == ReminderType.WEEKLY:
        lines.append(f"<b>Kun:</b> {reminder.day_of_week}")
    if reminder.type == ReminderType.MONTHLY:
        lines.append(f"<b>Har oyning:</b> {reminder.day_of_month}-sanasi")
    return "\n".join(lines)


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    user_tz = await firebase_service.get_user_timezone(message.from_user.id)
    today = now_in_tz(user_tz)
    reminders = await firebase_service.get_active_reminders_for_user(message.from_user.id)

    todays = []
    for r in reminders:
        if r.type == ReminderType.ONCE and r.target_datetime.date() == today.date():
            todays.append(r)
        elif r.type == ReminderType.DAILY:
            todays.append(r)
        elif r.type == ReminderType.WEEKLY and r.day_of_week and \
                r.day_of_week.lower() == today.strftime("%A").lower():
            todays.append(r)
        elif r.type == ReminderType.MONTHLY and r.day_of_month == today.day:
            todays.append(r)
        elif r.type == ReminderType.YEARLY and r.target_datetime.month == today.month \
                and r.target_datetime.day == today.day:
            todays.append(r)

    if not todays:
        await message.answer("Bugun uchun rejalashtirilgan eslatmalar yo'q.")
        return

    text = "📅 <b>Bugungi eslatmalar:</b>\n\n" + "\n".join(
        f"• {r.title} — {r.target_datetime.strftime('%H:%M')}" for r in todays
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    reminders = await firebase_service.get_active_reminders_for_user(message.from_user.id)
    if not reminders:
        await message.answer("Sizda faol eslatmalar yo'q.")
        return

    await message.answer(f"📋 Sizda {len(reminders)} ta faol eslatma bor:")
    for r in reminders:
        detail = f"{TYPE_LABELS.get(r.type.value, r.type.value)} — {r.title}\n" \
                  f"{r.target_datetime.strftime('%d.%m.%Y %H:%M')}"
        await message.answer(detail, reply_markup=reminder_list_item_keyboard(r.reminder_id))


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def on_free_text(message: Message, state: FSMContext) -> None:
    user_tz = await firebase_service.get_user_timezone(message.from_user.id)
    reference_now = now_in_tz(user_tz)

    try:
        parsed = await parse_reminder_text(message.text, reference_now, user_tz)
    except AIParseError:
        await message.answer(
            "Kechirasiz, hozir eslatmani tahlil qila olmadim. Birozdan so'ng qayta urinib ko'ring."
        )
        return

    if not parsed.is_valid or parsed.target_datetime is None:
        await message.answer(INVALID_TEXT_REPLY)
        return

    try:
        reminder_type = ReminderType(parsed.type)
    except ValueError:
        await message.answer(INVALID_TEXT_REPLY)
        return

    target_dt = localize(parsed.target_datetime, user_tz)

    # Defensive correction: never blindly trust the model's date math.
    if reminder_type == ReminderType.WEEKLY and parsed.day_of_week:
        target_dt = ensure_weekly_consistency(target_dt, parsed.day_of_week, reference_now)

    reminder = Reminder(
        user_id=message.from_user.id,
        title=parsed.title,
        type=reminder_type,
        target_datetime=target_dt,
        day_of_week=parsed.day_of_week,
        day_of_month=parsed.day_of_month,
        timezone=user_tz,
    )

    try:
        reminder.validate()
    except ValueError as exc:
        logger.warning("AI output failed validation: %s", exc)
        await message.answer(INVALID_TEXT_REPLY)
        return

    await state.update_data(pending_reminder=reminder)
    await state.set_state(ReminderFlow.waiting_confirmation)
    await message.answer(
        _format_confirmation(reminder),
        parse_mode="HTML",
        reply_markup=confirm_reminder_keyboard(),
    )


@router.message(StateFilter(None), F.voice)
async def on_voice_message(message: Message, state: FSMContext, bot: Bot) -> None:
    user_tz = await firebase_service.get_user_timezone(message.from_user.id)
    reference_now = now_in_tz(user_tz)

    status_msg = await message.answer("🎙 Ovozli xabar tahlil qilinmoqda...")

    try:
        file = await bot.get_file(message.voice.file_id)
        file_bytes_io = await bot.download_file(file.file_path)
        audio_bytes = file_bytes_io.read()

        parsed = await parse_reminder_audio(
            audio_bytes=audio_bytes,
            mime_type="audio/ogg",
            current_time=reference_now,
            user_timezone=user_tz,
        )
    except Exception as exc:
        logger.exception("Voice parsing failed: %s", exc)
        await status_msg.edit_text(
            "Kechirasiz, ovozli xabarni tahlil qila olmadim. Qaytadan urinib ko'ring."
        )
        return

    if not parsed.is_valid or parsed.target_datetime is None:
        await status_msg.edit_text(INVALID_TEXT_REPLY)
        return

    try:
        reminder_type = ReminderType(parsed.type)
    except ValueError:
        await status_msg.edit_text(INVALID_TEXT_REPLY)
        return

    target_dt = localize(parsed.target_datetime, user_tz)

    if reminder_type == ReminderType.WEEKLY and parsed.day_of_week:
        target_dt = ensure_weekly_consistency(target_dt, parsed.day_of_week, reference_now)

    reminder = Reminder(
        user_id=message.from_user.id,
        title=parsed.title,
        type=reminder_type,
        target_datetime=target_dt,
        day_of_week=parsed.day_of_week,
        day_of_month=parsed.day_of_month,
        timezone=user_tz,
    )

    try:
        reminder.validate()
    except ValueError as exc:
        logger.warning("AI output failed validation: %s", exc)
        await status_msg.edit_text(INVALID_TEXT_REPLY)
        return

    await state.update_data(pending_reminder=reminder)
    await state.set_state(ReminderFlow.waiting_confirmation)
    await status_msg.edit_text(
        f"🎙 <b>Ovozli xabar tahlil qilindi:</b>\n\n" + _format_confirmation(reminder),
        parse_mode="HTML",
        reply_markup=confirm_reminder_keyboard(),
    )


@router.callback_query(StateFilter(ReminderFlow.waiting_confirmation), F.data == "confirm_reminder")
async def confirm_reminder(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reminder: Reminder = data.get("pending_reminder")
    await state.clear()

    if reminder is None:
        await callback.answer("Xatolik yuz berdi, qaytadan urinib ko'ring.", show_alert=True)
        return

    try:
        await firebase_service.save_reminder(reminder)
    except firebase_service.FirebaseError as exc:
        logger.error("Could not save reminder to Firebase: %s", exc)
        # Even if Firestore fails, schedule in-memory scheduler so user gets notification!
        scheduler_service.schedule_reminder(bot, reminder)
        await callback.message.edit_text(
            f"✅ Eslatma rejalashtirildi: <b>{reminder.title}</b>\n"
            f"{reminder.target_datetime.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML",
        )
        await callback.answer()
        return

    scheduler_service.schedule_reminder(bot, reminder)

    await callback.message.edit_text(
        f"✅ Eslatma saqlandi: <b>{reminder.title}</b>\n"
        f"{reminder.target_datetime.strftime('%d.%m.%Y %H:%M')}",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(StateFilter(ReminderFlow.waiting_confirmation), F.data == "cancel_reminder")
async def cancel_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()


@router.callback_query(F.data.startswith("delete:"))
async def delete_reminder(callback: CallbackQuery, bot: Bot) -> None:
    reminder_id = callback.data.split(":", 1)[1]
    await firebase_service.update_reminder_status(reminder_id, ReminderStatus.DELETED)
    scheduler_service.remove_job(reminder_id)
    await callback.message.edit_text("❌ Eslatma o'chirildi.")
    await callback.answer()
