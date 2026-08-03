import pytest

from app import config


def test_bot_token_is_required_when_bot_is_enabled(monkeypatch):
    monkeypatch.setattr(config, "BOT_ENABLED", True)
    monkeypatch.setattr(config, "TOKEN", "")
    monkeypatch.setattr(config, "ENVIRONMENT", "development")

    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        config.validate_runtime_configuration()


def test_api_only_mode_still_requires_bot_token_for_authentication(monkeypatch):
    monkeypatch.setattr(config, "BOT_ENABLED", False)
    monkeypatch.setattr(config, "TOKEN", "")
    monkeypatch.setattr(config, "MINI_APP_URL", "")
    monkeypatch.setattr(config, "ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        config.validate_runtime_configuration()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", True),
        ("YES", True),
        ("1", True),
        ("false", False),
        ("No", False),
        ("0", False),
    ],
)
def test_bot_enabled_accepts_documented_boolean_values(monkeypatch, value, expected):
    monkeypatch.setenv("BOT_ENABLED", value)

    assert (
        config._parse_boolean_environment_variable("BOT_ENABLED", "true") is expected
    )


def test_bot_enabled_rejects_unrecognized_value(monkeypatch):
    monkeypatch.setenv("BOT_ENABLED", "treu")

    with pytest.raises(RuntimeError, match="BOT_ENABLED must be one of"):
        config._parse_boolean_environment_variable("BOT_ENABLED", "true")


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
