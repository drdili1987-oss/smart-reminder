import calendar
from datetime import date
from typing import List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models.reminder import Reminder, ReminderType, VALID_WEEKDAYS, WEEKDAY_TO_CRON

MONTH_NAMES_UZ = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
    5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
    9: "Sentyabr", 10: "Oktyabr", 11: "Noyabr", 12: "Dekabr"
}


def confirm_reminder_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data="confirm_reminder")
    builder.button(text="❌ Bekor qilish", callback_data="cancel_reminder")
    builder.adjust(2)
    return builder.as_markup()


def notification_keyboard(reminder_id: str, reminder_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Bajarildi", callback_data=f"done:{reminder_id}")
    builder.button(text="⏰ +15 min", callback_data=f"snooze15:{reminder_id}")
    builder.button(text="⏰ +1 soat", callback_data=f"snooze60:{reminder_id}")
    builder.button(text="⏰ Ertaga shu vaqtda", callback_data=f"snooze1440:{reminder_id}")
    builder.adjust(1, 2, 1)
    return builder.as_markup()


def reminder_list_item_keyboard(reminder_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ O'chirish", callback_data=f"delete:{reminder_id}")
    return builder.as_markup()


def timezone_choice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 Toshkent (GMT+5)", callback_data="tz:Asia/Tashkent")
    builder.button(text="🌍 GMT+0 (London)", callback_data="tz:Etc/GMT")
    builder.button(text="🇷🇺 Moskva (GMT+3)", callback_data="tz:Europe/Moscow")
    builder.adjust(1)
    return builder.as_markup()


def categories_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💼 Ish", callback_data="cat:ish")
    builder.button(text="🛒 Xarid", callback_data="cat:xarid")
    builder.button(text="💊 Sog'liq", callback_data="cat:sogliq")
    builder.button(text="👤 Shaxsiy", callback_data="cat:shaxsiy")
    builder.button(text="📌 Boshqa", callback_data="cat:boshqa")
    builder.button(text="📋 Barcha eslatmalar", callback_data="cat:all")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def build_calendar_keyboard(year: int, month: int, active_reminders: List[Reminder]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    month_name = MONTH_NAMES_UZ.get(month, "")

    # Row 1: Header navigation
    builder.button(text="◄", callback_data=f"cal:nav:{prev_year}:{prev_month}")
    builder.button(text=f"{month_name} {year}", callback_data="cal:ignore")
    builder.button(text="►", callback_data=f"cal:nav:{next_year}:{next_month}")

    # Row 2: Weekdays
    for day_name in ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]:
        builder.button(text=day_name, callback_data="cal:ignore")

    # Find days with active reminders
    reminder_days = set()
    cal_matrix = calendar.monthcalendar(year, month)

    for r in active_reminders:
        dt = r.target_datetime
        if r.type in (ReminderType.ONCE, ReminderType.INTERVAL):
            if dt.year == year and dt.month == month:
                reminder_days.add(dt.day)
        elif r.type == ReminderType.DAILY:
            for week in cal_matrix:
                for day in week:
                    if day > 0:
                        reminder_days.add(day)
        elif r.type == ReminderType.WEEKLY and r.day_of_week:
            days_list = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            if r.day_of_week.lower() in days_list:
                w_idx = days_list.index(r.day_of_week.lower())
                for week in cal_matrix:
                    if week[w_idx] > 0:
                        reminder_days.add(week[w_idx])
        elif r.type == ReminderType.MONTHLY and r.day_of_month:
            reminder_days.add(r.day_of_month)
        elif r.type == ReminderType.YEARLY:
            if dt.month == month:
                reminder_days.add(dt.day)

    # Days grid
    for week in cal_matrix:
        for day in week:
            if day == 0:
                builder.button(text=" ", callback_data="cal:ignore")
            else:
                text = f"{day}🔴" if day in reminder_days else f"{day}"
                builder.button(text=text, callback_data=f"cal:day:{year}:{month}:{day}")

    row_widths = [3, 7] + [7] * len(cal_matrix)
    builder.adjust(*row_widths)
    return builder.as_markup()
