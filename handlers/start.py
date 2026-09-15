import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from config import DEFAULT_TIMEZONE
from keyboards.inline import timezone_choice_keyboard
from services import firebase_service

logger = logging.getLogger(__name__)
router = Router(name="start")

HELP_TEXT = (
    "🤖 <b>Smart Reminder Bot</b>\n\n"
    "Menga oddiy tilda eslatma yozing, men uni tushunib, o'z vaqtida eslataman.\n\n"
    "<b>Misollar:</b>\n"
    "• Ertaga 15:00 da tish shifokori\n"
    "• Har kuni 07:00 da dori ichish\n"
    "• Har dushanba 09:00 da yig'ilish\n"
    "• Har oyning 5-sanasida ijarani to'lash\n"
    "• Har yili 21-mart kuni bayram tabrigi\n\n"
    "<b>Buyruqlar:</b>\n"
    "/today — Bugungi eslatmalar\n"
    "/list — Barcha faol eslatmalar\n"
    "/help — Ushbu qo'llanma"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await firebase_service.upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name or "",
        timezone_name=DEFAULT_TIMEZONE,
    )
    await message.answer(
        "Assalomu alaykum! Men Smart Reminder Bot man.\n\n"
        "Avval vaqt zonangizni tanlang:",
        reply_markup=timezone_choice_keyboard(),
    )


@router.callback_query(F.data.startswith("tz:"))
async def on_timezone_chosen(callback: CallbackQuery) -> None:
    tz_name = callback.data.split(":", 1)[1]
    await firebase_service.set_user_timezone(callback.from_user.id, tz_name)
    await callback.message.edit_text(
        f"✅ Vaqt zonangiz {tz_name} qilib belgilandi.\n\n" + HELP_TEXT,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")
