"""Tests for scripts.probe_ilmu_capabilities: the verdict logic must not approve output the router would discard."""
from __future__ import annotations

import pytest

from app.agents.router_node import _CLASSIFY_SCHEMA, router_claude_model
from scripts.probe_ilmu_capabilities import Result, _guard, _positive_int, _schema_valid

_GOOD = {
    "language": "en",
    "domain": "tax",
    "intent": "income tax rate",
    "is_live_status_query": False,
    "place_name": None,
    "is_structured_parliament_query": False,
    "parliament_bill_number": None,
    "parliament_mp_query": None,
}


def test_conforming_output_is_valid() -> None:
    assert _schema_valid(_GOOD)
    assert _schema_valid({**_GOOD, "domain": None, "place_name": "Pelita"})


@pytest.mark.parametrize(
    "patch",
    [
        {"is_live_status_query": "false"},  # string where boolean required
        {"place_name": ["Pelita"]},  # list where string|null required
        {"parliament_mp_query": 5},
        {"intent": None},  # null not allowed for intent
        {"domain": "scam_check"},  # outside the enum
        {"language": "fr"},
        {"surprise": 1},  # additionalProperties false
    ],
)
def test_type_invalid_output_is_rejected(patch: dict) -> None:
    assert not _schema_valid({**_GOOD, **patch})


def test_missing_key_and_non_dict_are_rejected() -> None:
    assert not _schema_valid({k: v for k, v in _GOOD.items() if k != "intent"})
    assert not _schema_valid(["not", "a", "dict"])


def test_probe_checks_every_schema_property() -> None:
    assert set(_GOOD) == set(_CLASSIFY_SCHEMA["properties"])


def test_zero_or_negative_queries_are_rejected() -> None:
    import argparse

    for bad in ("0", "-3"):
        with pytest.raises(argparse.ArgumentTypeError):
            _positive_int(bad)
    assert _positive_int("4") == 4


def test_probe_uses_the_same_claude_model_as_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTER_CLAUDE_MODEL", "claude-test-model")
    assert router_claude_model() == "claude-test-model"


def _status_error(status: int, message: str) -> Exception:
    import httpx
    import openai

    request = httpx.Request("POST", "https://api.ilmu.ai/v1/chat/completions")
    return openai.APIStatusError(message, response=httpx.Response(status, request=request), body=None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "message", "verdict"),
    [
        (400, "Unsupported parameter: response_format", "REJECTED"),
        (400, "model 'ilmu-chat' does not exist", "ERROR"),  # wrong model, not a feature verdict
        (404, "route not found", "ERROR"),
        (422, "tools: extra fields not permitted", "REJECTED"),
        (503, "overloaded", "ERROR"),
    ],
)
async def test_guard_only_rejects_when_the_error_names_the_feature(status: int, message: str, verdict: str) -> None:
    async def probe() -> Result:
        raise _status_error(status, message)

    result = await _guard("x", probe, ("response_format", "tools"))
    assert result.verdict == verdict


@pytest.mark.asyncio
async def test_error_naming_an_unrelated_feature_is_not_a_rejection_of_the_tested_one() -> None:
    """Qodo finding: a 400 mentioning 'tools' during the json_schema probe must not read as a schema rejection."""
    from scripts.probe_ilmu_capabilities import _JSON_SCHEMA_TERMS, _TOOL_TERMS

    async def probe() -> Result:
        raise _status_error(400, "unsupported value for tools")

    assert (await _guard("schema", probe, _JSON_SCHEMA_TERMS)).verdict == "ERROR"
    assert (await _guard("tools", probe, _TOOL_TERMS)).verdict == "REJECTED"


@pytest.mark.asyncio
async def test_router_sample_errors_keep_their_status_and_message(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.probe_ilmu_capabilities as probe_mod

    async def failing_chat(**kwargs: object) -> None:
        raise _status_error(401, "invalid api key")

    monkeypatch.setattr(probe_mod, "_chat", failing_chat)
    plain, schema = await probe_mod.router_validity(["q1", "q2"])

    for result in (plain, schema):
        assert result.verdict == "ERROR"
        assert "401" in result.detail and "invalid api key" in result.detail
        assert "2 request errors" in result.detail
