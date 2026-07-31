import os
from pathlib import Path


def _load_env_file() -> None:
    path = Path(".env")
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

TOKEN = os.getenv("BOT_TOKEN", "")
ADMINS = [
    int(admin_id)
    for admin_id in os.getenv("SUPER_ADMIN_IDS", os.getenv("ADMINS", "")).split(",")
    if admin_id.strip()
]
DATABASE = os.getenv("DATABASE", os.getenv("DATABASE_URL", "data/wb_trainer.db").removeprefix("sqlite+aiosqlite:///").removeprefix("sqlite:///"))
MINI_APP_URL = os.getenv("MINI_APP_URL", "").rstrip("/")
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()]
DEV_AUTH_ENABLED = os.getenv("DEV_AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}
INIT_DATA_MAX_AGE = int(os.getenv("TELEGRAM_INIT_DATA_MAX_AGE", "3600"))
SESSION_SECRET = os.getenv("SESSION_SECRET", TOKEN or "development-only-change-me")
ATTEMPT_TTL_HOURS = int(os.getenv("ATTEMPT_TTL_HOURS", "24"))

if ENVIRONMENT == "production" and DEV_AUTH_ENABLED:
    raise RuntimeError("DEV_AUTH_ENABLED must be false in production")
