"""Тесты загрузки и проверки конфигурации."""

import base64

import pytest

from config import Config, ConfigError, _get_bool, _get_int, load_config

_REQUIRED = (
    "VK_GROUP_TOKEN",
    "VK_GROUP_ID",
    "GIGACHAT_AUTH_KEY",
    "GIGACHAT_CLIENT_ID",
    "GIGACHAT_CLIENT_SECRET",
)


def test_auth_key_prefers_explicit_key(monkeypatch):
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "explicit")
    monkeypatch.setenv("GIGACHAT_CLIENT_ID", "id")
    monkeypatch.setenv("GIGACHAT_CLIENT_SECRET", "secret")
    assert Config().auth_key == "explicit"


def test_auth_key_built_from_client_credentials(monkeypatch):
    monkeypatch.delenv("GIGACHAT_AUTH_KEY", raising=False)
    monkeypatch.setenv("GIGACHAT_CLIENT_ID", "id")
    monkeypatch.setenv("GIGACHAT_CLIENT_SECRET", "secret")

    expected = base64.b64encode(b"id:secret").decode("ascii")
    assert Config().auth_key == expected


def test_auth_key_empty_without_credentials(monkeypatch):
    for name in ("GIGACHAT_AUTH_KEY", "GIGACHAT_CLIENT_ID", "GIGACHAT_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    assert Config().auth_key == ""


def test_validate_raises_when_required_missing(monkeypatch):
    for name in _REQUIRED:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError):
        load_config()


def test_validate_passes_when_configured(monkeypatch):
    monkeypatch.setenv("VK_GROUP_TOKEN", "token")
    monkeypatch.setenv("VK_GROUP_ID", "123")
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "key")
    load_config()


def test_defaults_are_applied(monkeypatch):
    monkeypatch.delenv("GIGACHAT_MODEL", raising=False)
    monkeypatch.delenv("MAX_HISTORY_TURNS", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    config = Config()

    assert config.gigachat_model == "GigaChat-2"
    assert config.max_history_turns == 10
    assert config.log_level == "INFO"


def test_get_bool_and_get_int_helpers(monkeypatch):
    monkeypatch.setenv("FLAG", "yes")
    monkeypatch.setenv("NUM", "42")
    assert _get_bool("FLAG", False) is True
    assert _get_int("NUM", 0) == 42

    monkeypatch.setenv("NUM", "not-a-number")
    assert _get_int("NUM", 7) == 7
