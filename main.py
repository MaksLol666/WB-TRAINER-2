import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import TOKEN
from app.database import init_db
from app.handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    print("🚀 WB TRAINER запускается...")
    await init_db()
    print("✅ База данных готова")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
