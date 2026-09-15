from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def confirm_reminder_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data="confirm_reminder")
    builder.button(text="❌ Bekor qilish", callback_data="cancel_reminder")
    builder.adjust(2)
    return builder.as_markup()


def notification_keyboard(reminder_id: str, reminder_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Bajarildi", callback_data=f"done:{reminder_id}")
    if reminder_type == "once":
        builder.button(text="⏰ +15 daqiqa", callback_data=f"snooze15:{reminder_id}")
        builder.button(text="⏰ +1 soat", callback_data=f"snooze60:{reminder_id}")
        builder.adjust(1, 2)
    else:
        builder.adjust(1)
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
