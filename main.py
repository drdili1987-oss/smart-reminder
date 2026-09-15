import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from aiogram.types import BotCommand

from config import BOT_TOKEN
from handlers import start, reminders, callbacks
from services.scheduler_service import start_scheduler, reschedule_all

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="today", description="📅 Bugungi eslatmalar"),
        BotCommand(command="list", description="📋 Barcha faol eslatmalar"),
        BotCommand(command="categories", description="📂 Kategoriyalar bo'yicha saralash"),
        BotCommand(command="calendar", description="📆 Interaktiv taqvim"),
        BotCommand(command="voice_help", description="🎧 Ovozli yo'riqnoma"),
        BotCommand(command="help", description="💡 Bot imkoniyatlari va qo'llanma"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(reminders.router)
    dp.include_router(callbacks.router)

    await set_bot_commands(bot)

    start_scheduler()
    restored = await reschedule_all(bot)
    logger.info("Startup complete. %d reminder(s) restored into scheduler.", restored)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
