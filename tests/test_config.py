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


def test_runtime_summary_reports_presence_without_leaking_secrets(monkeypatch):
    monkeypatch.setattr(config, "BOT_ENABLED", True)
    monkeypatch.setattr(config, "TOKEN", "secret-bot-token")
    monkeypatch.setattr(config, "MINI_APP_URL", "https://trainer.example")
    monkeypatch.setattr(config, "ENVIRONMENT", "production")

    summary = config.runtime_configuration_summary()

    assert "environment=production" in summary
    assert "bot_enabled=True" in summary
    assert "bot_token_configured=True" in summary
    assert "mini_app_url_configured=True" in summary
    assert "secret-bot-token" not in summary
    assert "trainer.example" not in summary
