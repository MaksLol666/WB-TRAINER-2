import pytest

from app import config


def test_bot_token_is_required_when_bot_is_enabled(monkeypatch):
    monkeypatch.setattr(config, "BOT_ENABLED", True)
    monkeypatch.setattr(config, "TOKEN", "")
    monkeypatch.setattr(config, "ENVIRONMENT", "development")

    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        config.validate_runtime_configuration()


def test_api_only_mode_does_not_require_telegram_settings(monkeypatch):
    monkeypatch.setattr(config, "BOT_ENABLED", False)
    monkeypatch.setattr(config, "TOKEN", "")
    monkeypatch.setattr(config, "MINI_APP_URL", "")
    monkeypatch.setattr(config, "ENVIRONMENT", "production")

    config.validate_runtime_configuration()


def test_production_bot_requires_mini_app_url(monkeypatch):
    monkeypatch.setattr(config, "BOT_ENABLED", True)
    monkeypatch.setattr(config, "TOKEN", "valid-token")
    monkeypatch.setattr(config, "MINI_APP_URL", "")
    monkeypatch.setattr(config, "ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="MINI_APP_URL"):
        config.validate_runtime_configuration()
