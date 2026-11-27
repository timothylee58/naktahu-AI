"""Tests for scripts.probe_ilmu_capabilities: the verdict logic must not approve output the router would discard."""
from __future__ import annotations

import pytest

from app.agents.router_node import _CLASSIFY_SCHEMA, router_claude_model
from scripts.probe_ilmu_capabilities import _positive_int, _schema_valid

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
