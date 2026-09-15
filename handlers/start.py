import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from config import DEFAULT_TIMEZONE
from keyboards.inline import timezone_choice_keyboard, help_topics_keyboard
from services import firebase_service, tts_service

logger = logging.getLogger(__name__)
router = Router(name="start")

HELP_TEXT = (
    "🤖 <b>Smart Reminder Bot — Nimalarga qodir?</b>\n\n"
    "Bot sizning matnli, ovozli va tasvirli ko'rsatmalaringizni sun'iy intellekt (Gemini AI) yordamida tahlil qiladi hamda o'z vaqtida eslatadi!\n\n"
    "📌 <b>Asosiy buyruqlar:</b>\n"
    "• /today — Bugungi eslatmalar\n"
    "• /list — Barcha faol eslatmalar\n"
    "• /categories — Kategoriyalar bo'yicha ko'rish\n"
    "• /calendar — Interaktiv oylik taqvim\n"
    "• /voice_help — 🎧 Ovozli yo'riqnoma\n"
    "• /help — Ushbu qo'llanma va yo'riqnoma\n\n"
    "👇 <b>Batafsil ma'lumot va misollar uchun pastdagi bo'limlarni tanlang:</b>"
)

VOICE_HELP_TEXT = (
    "Assalomu alaykum! Men Smart Reminder Botman, sizning shaxsiy eslatuvchi yordamchingizman. "
    "Menga xabaringizni yozib yuborasizmi, ovozli xabar qilasizmi yoki rasm biriktirasizmi — barchasini osongina tushunaman va belgilangan vaqtda eslataman. "
    "Masalan, 'har 2 soatda suv ichishni eslat' desangiz, intervalli eslatma qo'yib beraman. "
    "Eslatma kelganida esa, uni 15 daqiqa yoki 1 soatga kechiktirish tugmalaridan foydalanishingiz mumkin. "
    "Barcha rejalaringizni kategoriyalar hamda taqvim bo'limida qulay ko'rishingiz mumkin."
)

HELP_TOPICS = {
    "voice": (
        "🎙 <b>Ovozli xabar orqali eslatma yaratish:</b>\n\n"
        "Matn yozib o'tirish shart emas! Shunchaki botga ovozli xabar (Voice Note) yuboring.\n\n"
        "<b>Misollar:</b>\n"
        "• <i>'Ertaga soat 15:00 da tish shifokoriga borishni eslat'</i>\n"
        "• <i>'Har kuni kechki soat 20:00 da ingliz tili darsi'</i>\n"
        "• <i>'Har 2 soatda suv ichishni eslat'</i>\n\n"
        "⚡️ Bot ovozingizni avtomatik matnga o'giradi va eslatma jadvaliga qo'shadi."
    ),
    "files": (
        "📷 <b>Rasm va Hujjat biriktirish:</b>\n\n"
        "Retsept rasmi, chipta yoki hujjatni botga yuborib, izoh (caption) sifatida vaqtini yozing.\n\n"
        "<b>Misol:</b>\n"
        "• Rasm yuborasiz + izoh: <i>'Ertaga 10:00 da ushbu dorini sotib olish'</i>\n"
        "• Hujjat yuborasiz + izoh: <i>'Juma kuni 14:00 da ushbu shartnomani topshirish'</i>\n\n"
        "⚡️ Eslatma vaqti kelganida bot matn bilan birga o'sha rasm/faylni ham yuboradi!"
    ),
    "interval": (
        "⏱ <b>Interval Eslatmalar va Smart Snooze:</b>\n\n"
        "<b>Interval eslatmalar:</b>\n"
        "• <i>'Har 2 soatda suv ichish'</i>\n"
        "• <i>'Har 30 minutda mashq bajarish'</i>\n\n"
        "<b>Smart Snooze (Kechiktirish):</b>\n"
        "Eslatma kelganida xabarning ostida <code>[⏰ +15 min]</code>, <code>[⏰ +1 soat]</code>, <code>[⏰ Ertaga shu vaqtda]</code> tugmalari chiqadi."
    ),
    "categories": (
        "📂 <b>Kategoriyalar va Teglar:</b>\n\n"
        "Bot barcha eslatmalaringizni sun'iy intellekt yordamida avtomatik saralaydi:\n"
        "• 💼 <b>#ish</b> — Yig'ilish va topshiriqlar\n"
        "• 🛒 <b>#xarid</b> — Do'kon va bozordan sotib olinadigan narsalar\n"
        "• 💊 <b>#sogliq</b> — Dori va mashg'ulotlar\n"
        "• 👤 <b>#shaxsiy</b> — Tug'ilgan kunlar va shaxsiy rejalari\n\n"
        "Siz <code>/categories</code> buyrug'i orqali ma'lum bir turdagi eslatmalarni saralab ko'rishingiz mumkin."
    ),
    "group": (
        "👥 <b>Guruh va Jamoaviy eslatmalar:</b>\n\n"
        "Botni ishchi yoki jamoaviy Telegram guruhlariga qo'shishingiz mumkin!\n\n"
        "Guruhda eslatma yaratilganda bot eslatmani kim yaratganini eslab qoladi va belgilangan vaqtda butun jamoaga eslatadi."
    ),
    "calendar": (
        "📅 <b>Interaktiv Oylik Taqvim:</b>\n\n"
        "<code>/calendar</code> buyrug'ini yuborsangiz, Telegram ichida oylik tugmali taqvim chiqadi.\n\n"
        "• Eslatma bor kunlar 🔴 belgisi bilan ajratib ko'rsatiladi.\n"
        "• Kunning ustiga bosib, o'sha kundagi eslatmalar ro'yxatini ko'rishingiz mumkin."
    ),
}


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
        reply_markup=help_topics_keyboard(),
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=help_topics_keyboard(),
    )


import time


async def _send_voice_help(chat_id: int, bot_or_message) -> None:
    status_msg = await bot_or_message.answer("🎙 Ovozli yo'riqnoma yaratilmoqda...")
    audio_bytes = await tts_service.text_to_speech_bytes(VOICE_HELP_TEXT)
    if audio_bytes:
        filename = f"voice_help_male_natural_{int(time.time())}.ogg"
        voice_file = BufferedInputFile(audio_bytes, filename=filename)
        await bot_or_message.answer_voice(
            voice=voice_file,
            caption="🎧 <b>Smart Reminder Bot — Ovozli Yo'riqnoma (Erkak ovozi)</b>",
            parse_mode="HTML",
        )
        await status_msg.delete()
    else:
        await status_msg.edit_text("Kechirasiz, ovozli yo'riqnomani yaratishda xatolik yuz berdi.")


@router.message(Command("voice_help"))
async def cmd_voice_help(message: Message) -> None:
    await _send_voice_help(message.chat.id, message)


@router.callback_query(F.data.startswith("help:"))
async def on_help_topic(callback: CallbackQuery) -> None:
    topic_key = callback.data.split(":", 1)[1]
    if topic_key == "voice_audio":
        await _send_voice_help(callback.message.chat.id, callback.message)
        await callback.answer()
        return

    topic_text = HELP_TOPICS.get(topic_key, HELP_TEXT)
    await callback.message.answer(
        topic_text,
        parse_mode="HTML",
        reply_markup=help_topics_keyboard(),
    )
    await callback.answer()
