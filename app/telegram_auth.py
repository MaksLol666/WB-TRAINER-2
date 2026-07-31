import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from urllib.parse import parse_qsl

from app.config import INIT_DATA_MAX_AGE, SESSION_SECRET, TOKEN


class AuthError(ValueError):
    pass


@dataclass(frozen=True)
class TelegramIdentity:
    telegram_id: int
    first_name: str
    last_name: str = ""
    username: str | None = None
    photo_url: str | None = None

    @property
    def full_name(self) -> str:
        return " ".join(filter(None, (self.first_name, self.last_name))).strip() or "Пользователь Telegram"


def validate_init_data(init_data: str, *, now: int | None = None) -> TelegramIdentity:
    if not TOKEN:
        raise AuthError("BOT_TOKEN is not configured")
    values = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    received_hash = values.pop("hash", None)
    if not received_hash:
        raise AuthError("Missing Telegram hash")
    auth_date = int(values.get("auth_date", "0"))
    current = int(time.time()) if now is None else now
    if auth_date <= 0 or current - auth_date > INIT_DATA_MAX_AGE or auth_date > current + 30:
        raise AuthError("Telegram data has expired")
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise AuthError("Invalid Telegram signature")
    try:
        user = json.loads(values["user"])
        return TelegramIdentity(
            telegram_id=int(user["id"]), first_name=str(user.get("first_name", "")),
            last_name=str(user.get("last_name", "")), username=user.get("username"),
            photo_url=user.get("photo_url"),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthError("Invalid Telegram user data") from exc


def create_session(user_id: int, ttl_seconds: int = 86400) -> str:
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + ttl_seconds}, separators=(",", ":")).encode()
    encoded = urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(SESSION_SECRET.encode(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def verify_session(token: str) -> int:
    try:
        encoded, supplied = token.split(".", 1)
        raw = encoded.encode()
        expected = hmac.new(SESSION_SECRET.encode(), raw, hashlib.sha256).digest()
        signature = urlsafe_b64decode(supplied + "=" * (-len(supplied) % 4))
        if not hmac.compare_digest(expected, signature):
            raise AuthError("Invalid session")
        payload = json.loads(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise AuthError("Session expired")
        return int(payload["uid"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        if isinstance(exc, AuthError):
            raise
        raise AuthError("Invalid session") from exc
