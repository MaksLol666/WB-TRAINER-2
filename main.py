import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import TOKEN
from app.database import init_db
from app.handlers import rou
from app.api import create_app
from app.bot_setup import configure_bot_menu
from app.config import WEBAPP_HOST, WEBAPP_PORT
from app.services import import_questions
import uvicorn


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def run_bot():
    if not TOKEN:
        logging.warning("BOT_TOKEN is empty; API starts without Telegram polling")
        return
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage()); dp.include_router(router)
    try:
        await configure_bot_menu(bot)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def main():
    print("🚀 WB TRAINER API и бот запускаются...")
    await init_db()
    created, updated = await import_questions()
    logging.info("question bank synchronized: created=%s updated=%s", created, updated)
    server = uvicorn.Server(uvicorn.Config(create_app(), host=WEBAPP_HOST, port=WEBAPP_PORT, log_level="info"))
    await asyncio.gather(server.serve(), run_bot())

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
