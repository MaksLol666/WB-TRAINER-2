import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.api import create_app
from app.bot_setup import configure_bot_menu
from app.config import TOKEN, WEBAPP_HOST, WEBAPP_PORT
from app.database import init_db
from app.handlers import router
from app.services import import_questions


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def run_bot() -> None:
    """Run Telegram polling when a bot token has been configured."""
    if not TOKEN:
        logging.warning("BOT_TOKEN is empty; API starts without Telegram polling")
        return

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    try:
        await configure_bot_menu(bot)
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


async def main() -> None:
    """Initialize shared data, then run the API and Telegram bot together."""
    logging.info("WB TRAINER API and bot are starting")
    await init_db()
    created, updated = await import_questions()
    logging.info(
        "question bank synchronized: created=%s updated=%s", created, updated
    )

    server = uvicorn.Server(
        uvicorn.Config(
            create_app(),
            host=WEBAPP_HOST,
            port=WEBAPP_PORT,
            log_level="info",
        )
    )
    await asyncio.gather(server.serve(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
