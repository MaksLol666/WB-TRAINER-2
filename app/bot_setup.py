import logging

from aiogram import Bot
from aiogram.types import BotCommand, MenuButtonCommands, MenuButtonWebApp, WebAppInfo

from app.config import MINI_APP_URL

log = logging.getLogger(__name__)


async def configure_bot_menu(bot: Bot) -> None:
    """Configure commands and the persistent Telegram chat menu button."""
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть WB TRAINER"),
            BotCommand(command="menu", description="Показать резервное меню"),
        ]
    )
    if MINI_APP_URL:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть WB TRAINER",
                web_app=WebAppInfo(url=MINI_APP_URL),
            )
        )
        log.info("Telegram Mini App menu button configured")
    else:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        log.warning("MINI_APP_URL is empty; Telegram command menu is used")
