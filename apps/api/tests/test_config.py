"""Tests for core.config — the JWT secret must never fall back to a fixed,
publicly-known default (a forgeable-token vulnerability if JWT_SECRET is
ever left unset in a real deployment)."""
from __future__ import annotations

import importlib

import pytest

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


def test_jwt_secret_raises_in_production_when_unset(monkeypatch):
    """A random per-process secret is fine for a single test/dev process,
    but Railway runs multiple workers/containers in production — each
    minting its own random secret would reject tokens signed by the
    others (intermittent 401s). Production must fail loudly at startup
    instead of failing open OR failing randomly-per-worker.

    _IS_PRODUCTION is computed once at module import time, so the reload
    itself — not a later Settings() call — is what re-evaluates ENV and
    triggers the module-level `settings = Settings()` line; that's where
    the RuntimeError actually raises.
    """
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    import core.config as config_module
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET is not set"):
            importlib.reload(config_module)
    finally:
        # Leave the module in a working state for every test that runs
        # after this one in the same process.
        monkeypatch.undo()
        importlib.reload(config_module)


def test_jwt_secret_production_with_explicit_secret_does_not_raise(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-production-secret-value")
    import core.config as config_module
    try:
        importlib.reload(config_module)
        assert config_module.settings.jwt_secret == "a-real-production-secret-value"
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)


def test_guard_llm_check_disabled_by_default(monkeypatch):
    """Regression: production observed the ILMU-backed soft classifier in
    guard_node wrongly flag three unrelated benign civic queries (lost ID
    document, contacting an MP, registering a company) as harmful despite
    two rounds of system-prompt tuning. Defaults OFF until the classifier's
    real-world false-positive rate is investigated — the hard keyword
    layer (_is_blocked_intent) is unaffected by this setting and stays
    fully active either way."""
    monkeypatch.delenv("GUARD_LLM_CHECK_ENABLED", raising=False)
    s = Settings()
    assert s.guard_llm_check_enabled is False


def test_guard_llm_check_still_respects_explicit_env_var(monkeypatch):
    monkeypatch.setenv("GUARD_LLM_CHECK_ENABLED", "true")
    s = Settings()
    assert s.guard_llm_check_enabled is True
