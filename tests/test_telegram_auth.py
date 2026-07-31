import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

import app.telegram_auth as auth


def make_init_data(token: str, auth_date: int, user_id: int = 42) -> str:
    fields = {"auth_date": str(auth_date), "query_id": "AAE-test", "user": json.dumps({"id": user_id, "first_name": "Иван", "username": "ivan"}, separators=(",", ":"), ensure_ascii=False)}
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class TelegramAuthTests(unittest.TestCase):
    def test_valid_signature(self):
        now = int(time.time()); token = "123:test"
        with patch.object(auth, "TOKEN", token), patch.object(auth, "INIT_DATA_MAX_AGE", 3600):
            identity = auth.validate_init_data(make_init_data(token, now), now=now)
        self.assertEqual(identity.telegram_id, 42); self.assertEqual(identity.username, "ivan")

    def test_rejects_invalid_signature(self):
        now = int(time.time())
        with patch.object(auth, "TOKEN", "real"):
            with self.assertRaises(auth.AuthError): auth.validate_init_data(make_init_data("wrong", now), now=now)

    def test_rejects_expired_data(self):
        now = int(time.time()); token = "123:test"
        with patch.object(auth, "TOKEN", token), patch.object(auth, "INIT_DATA_MAX_AGE", 60):
            with self.assertRaisesRegex(auth.AuthError, "expired"): auth.validate_init_data(make_init_data(token, now - 61), now=now)

    def test_session_round_trip_and_tamper(self):
        with patch.object(auth, "SESSION_SECRET", "secret"):
            token = auth.create_session(17)
            self.assertEqual(auth.verify_session(token), 17)
            with self.assertRaises(auth.AuthError): auth.verify_session(token + "x")
