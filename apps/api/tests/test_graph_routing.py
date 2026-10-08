"""Tests for app.agents.graph's post-analyst routing.

_route_after_analyst is a pure function (no LLM/DB calls), so these are
plain unit tests rather than async/mocked ones.
"""
from __future__ import annotations

import pytest

from app.agents.clarification import clarification_message
from app.agents.graph import _clarification_node, _route_after_analyst
from app.services.vector_store import ChunkResult


def _chunk() -> ChunkResult:
    return ChunkResult(
        id="c1",
        content="some retrieved content",
        source_title="Some Source",
        source_url="https://www.hasil.gov.my/some-source",
        ministry="LHDN",
        language="en",
        similarity=0.7,
    )


def test_confident_answer_routes_to_synthesiser() -> None:
    state = {"needs_clarification": False, "retrieved_chunks": [_chunk()]}
    assert _route_after_analyst(state) == "synthesiser"


def test_low_confidence_with_chunks_routes_to_synthesiser_not_clarification() -> None:
    """The behaviour this change adds: low confidence with SOME retrieved
    material still goes to the synthesiser (which hedges + asks a targeted
    follow-up) instead of the bare clarification node."""
    state = {"needs_clarification": True, "retrieved_chunks": [_chunk()]}
    assert _route_after_analyst(state) == "synthesiser"


def test_low_confidence_with_no_chunks_routes_to_clarification() -> None:
    """The narrower case that still gets the bare clarification node: nothing
    at all was retrieved, so there's no material to hedge an answer from."""
    state = {"needs_clarification": True, "retrieved_chunks": []}
    assert _route_after_analyst(state) == "clarification"


def test_low_confidence_with_missing_chunks_key_routes_to_clarification() -> None:
    """retrieved_chunks absent from state (not just empty) must behave the
    same as an empty list — state.get(...) default, not a KeyError."""
    state = {"needs_clarification": True}
    assert _route_after_analyst(state) == "clarification"


# ── Clarification message (bm / en / zh) ─────────────────────────────────

def test_chinese_query_gets_a_chinese_clarification_not_english() -> None:
    """Regression: only bm and en existed, so zh fell through to English."""
    msg = _clarification_node({"language": "zh"})["streaming_token_buffer"]
    assert msg == clarification_message("zh")
    assert "抱歉" in msg
    assert "confident" not in msg


@pytest.mark.parametrize(
    ("language", "expected_fragment"),
    [("bm", "Maaf"), ("en", "not confident enough"), ("zh", "抱歉")],
)
def test_clarification_message_per_language(language: str, expected_fragment: str) -> None:
    assert expected_fragment in clarification_message(language)


@pytest.mark.parametrize("language", [None, "", "fr", "ms"])
def test_clarification_message_falls_back_to_english(language: str | None) -> None:
    assert clarification_message(language) == clarification_message("en")


def test_clarification_node_defaults_to_english_when_language_missing() -> None:
    msg = _clarification_node({})["streaming_token_buffer"]
    assert msg == clarification_message("en")
