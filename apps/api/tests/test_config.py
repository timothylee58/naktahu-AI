"""Tests for core.config — the JWT secret must never fall back to a fixed,
publicly-known default (a forgeable-token vulnerability if JWT_SECRET is
ever left unset in a real deployment)."""
from __future__ import annotations

import importlib

from core.config import Settings


def test_jwt_secret_default_is_not_the_old_known_string(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    s = Settings()
    assert s.jwt_secret != "dev-jwt-secret-change-me-min-32-chars!!"


def test_jwt_secret_default_is_reasonably_long(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    s = Settings()
    assert len(s.jwt_secret) >= 32


def test_jwt_secret_still_respects_explicit_env_var(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "an-explicitly-configured-secret-value")
    s = Settings()
    assert s.jwt_secret == "an-explicitly-configured-secret-value"


def test_jwt_secret_stable_within_a_single_process(monkeypatch):
    """The random fallback must not regenerate on every Settings() call —
    otherwise a token signed by one instantiation would fail verification
    against another within the same running process."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    import core.config as config_module
    importlib.reload(config_module)
    a = config_module.Settings()
    b = config_module.Settings()
    assert a.jwt_secret == b.jwt_secret
