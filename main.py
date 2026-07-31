import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import TOKEN
from app.database import init_db
from app.handlers import router
from app.api import create_app
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
    await dp.start_polling(bot)


async def main():
    print("🚀 WB TRAINER API и бот запускаются...")
    await init_db()
    created, updated = await import_questions()
    logging.info("question bank synchronized: created=%s updated=%s", created, updated)
    server = uvicorn.Server(uvicorn.Config(create_app(), host=WEBAPP_HOST, port=WEBAPP_PORT, log_level="info"))
    await asyncio.gather(server.serve(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
