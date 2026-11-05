"""Configuration never falls back to unsafe modes or exposes key material."""

import pytest

from veilmint.config import Settings


def test_safe_default_mode_and_hidden_key(monkeypatch):
    monkeypatch.delenv("VEILMINT_MODE", raising=False)
    monkeypatch.setenv("VEILMINT_HMAC_KEY", "SYNTHETIC-CONFIG-KEY-DO-NOT-USE-LIVE")
    settings = Settings.from_env()
    assert settings.mode.value == "OBSERVE"
    assert settings.hmac_key is not None
    assert "SYNTHETIC-CONFIG-KEY" not in repr(settings)


def test_invalid_settings_do_not_echo_supplied_values(monkeypatch):
    marker = "SYNTHETIC_SECRET_IN_INVALID_MODE"
    monkeypatch.setenv("VEILMINT_MODE", marker)
    with pytest.raises(ValueError) as error:
        Settings.from_env()
    assert marker not in str(error.value)
    with pytest.raises(ValueError) as key_error:
        Settings(hmac_key=b"short-secret")
    assert "short-secret" not in str(key_error.value)
