import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "")
ADMINS = [int(admin_id) for admin_id in os.getenv("ADMINS", "1691654877").split(",") if admin_id.strip()]
DATABASE = os.getenv("DATABASE", "wb_trainer.db")
