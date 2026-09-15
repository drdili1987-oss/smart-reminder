"""
Parses free-form Uzbek/Russian/English text, voice messages, or photos into a
structured reminder with automated category tagging using Google Gemini API.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT_TEMPLATE = (
    "Siz matn, rasm yoki audio xabardan eslatma tafsilotlarini ajratib oluvchi va kategoriyalovchi yordamchisiz. "
    "Foydalanuvchining joriy vaqti: {current_time}, vaqt zonasi: {user_timezone}. "
    "Xabardan/rasmdan eslatma mazmuni, sanasi, vaqti, takrorlanish turi hamda mos kategoriyasini aniqlang "
    "hamda qat'iy belgilangan JSON formatida qaytaring. "
    "Javobda faqat JSON bo'lsin, hech qanday izoh yoki matn qo'shmang.\n\n"
    "JSON schema:\n"
    "{{\n"
    '  "title": string,\n'
    '  "type": "once" | "daily" | "weekly" | "monthly" | "yearly",\n'
    '  "category": "ish" | "xarid" | "sogliq" | "shaxsiy" | "boshqa",\n'
    '  "target_datetime": "DD.MM.YYYY HH:MM",\n'
    '  "day_of_week": "monday".."sunday" | null,\n'
    '  "day_of_month": 1-31 | null,\n'
    '  "is_valid": boolean\n'
    "}}\n\n"
    "Qoidalar:\n"
    "- 'category': Yig'ilish, uchrashuv, topshiriq bo'lsa 'ish'; bozor, do'kon, sotib olish bo'lsa 'xarid'; dori, shifokor, mashg'ulot bo'lsa 'sogliq'; shaxsiy reja, tug'ilgan kun bo'lsa 'shaxsiy'; qolgan hollarda 'boshqa' deb belgilang.\n"
    "- Agar xabar eslatmaga aloqador bo'lmasa yoki vaqt/sana aniqlanmasa, is_valid=false qaytaring.\n"
    "- 'once' uchun target_datetime to'liq sana+vaqt bo'lishi shart.\n"
    "- 'weekly' uchun day_of_week to'ldirilishi shart, target_datetime shu haftadagi eng yaqin mos kunga qo'yiladi.\n"
    "- 'monthly' uchun day_of_month to'ldirilishi shart.\n"
    "- 'daily'/'yearly' uchun faqat vaqt (va yearly uchun oy/kun ham) muhim.\n"
    "- Javobdagi barcha sana/vaqtlar foydalanuvchi vaqt zonasida bo'lishi kerak."
)


@dataclass
class ParsedReminder:
    title: str
    type: str
    target_datetime: Optional[datetime]
    day_of_week: Optional[str]
    day_of_month: Optional[int]
    is_valid: bool
    category: str = "boshqa"


class AIParseError(Exception):
    pass


async def _generate_parsed_reminder(
    contents: Union[str, list], system_prompt: str
) -> ParsedReminder:
    models_to_try = [GEMINI_MODEL, "gemini-3.5-flash", "gemini-3.5-flash-lite"]
    seen = set()
    models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    last_exc = None
    response_text = None

    for model_name in models:
        try:
            response = await _client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    system_instruction=system_prompt,
                    temperature=0,
                    max_output_tokens=1000,
                ),
            )
            response_text = response.text
            break
        except Exception as exc:
            logger.warning("Gemini API call to %s failed: %s", model_name, exc)
            last_exc = exc

    if response_text is None:
        logger.exception("All Gemini API models failed")
        raise AIParseError(str(last_exc)) from last_exc

    try:
        data = json.loads(response_text)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Non-JSON response from Gemini model: %r", response_text)
        raise AIParseError("model returned invalid JSON") from exc

    is_valid = bool(data.get("is_valid", False))
    dt_str = data.get("target_datetime")
    parsed_dt = None
    if dt_str:
        for fmt in ("%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M"):
            try:
                parsed_dt = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                pass
        if parsed_dt is None:
            logger.warning("Unparseable target_datetime %r, marking invalid", dt_str)
            is_valid = False

    cat = (data.get("category") or "boshqa").lower()
    if cat not in ("ish", "xarid", "sogliq", "shaxsiy", "boshqa"):
        cat = "boshqa"

    return ParsedReminder(
        title=(data.get("title") or "").strip(),
        type=data.get("type", "once"),
        category=cat,
        target_datetime=parsed_dt,
        day_of_week=(data.get("day_of_week") or None),
        day_of_month=data.get("day_of_month"),
        is_valid=is_valid and bool(data.get("title")),
    )


async def parse_reminder_text(
    text: str, current_time: datetime, user_timezone: str
) -> ParsedReminder:
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        current_time=current_time.strftime("%d.%m.%Y %H:%M (%A)"),
        user_timezone=user_timezone,
    )
    return await _generate_parsed_reminder(text, system_prompt)


async def parse_reminder_audio(
    audio_bytes: bytes, mime_type: str, current_time: datetime, user_timezone: str
) -> ParsedReminder:
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        current_time=current_time.strftime("%d.%m.%Y %H:%M (%A)"),
        user_timezone=user_timezone,
    )
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    contents = [
        audio_part,
        "Ushbu audio yozuvdagi so'zlarni va eslatma ma'lumotlarini tahlil qiling va faqat JSON formatida qaytaring."
    ]
    return await _generate_parsed_reminder(contents, system_prompt)


async def parse_reminder_image(
    image_bytes: bytes, mime_type: str, caption: str, current_time: datetime, user_timezone: str
) -> ParsedReminder:
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        current_time=current_time.strftime("%d.%m.%Y %H:%M (%A)"),
        user_timezone=user_timezone,
    )
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    prompt_text = (
        f"Ushbu rasmdagi va izohdagi ({caption}) eslatma tafsilotlarini aniqlang va faqat JSON formatida qaytaring."
        if caption else
        "Ushbu rasmdagi matn va ma'lumotlardan eslatma tafsilotlarini ajratib olib, faqat JSON formatida qaytaring."
    )
    contents = [image_part, prompt_text]
    return await _generate_parsed_reminder(contents, system_prompt)
