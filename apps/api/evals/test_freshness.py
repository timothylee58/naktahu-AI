"""Freshness eval gate — catches stale-but-faithful answers.

RAGAS-style **faithfulness** (and this repo's `answer_quality` confidence gate)
only measure *answer-to-chunk* consistency — never *chunk-to-reality* accuracy.
So a stale chunk reproduced perfectly scores fully faithful while being
factually wrong, with a real gov.my citation, and a faithfulness/confidence-only
gate never catches it. Concretely:

    EPF Budget 2023: withdrawal cap = RM1,000   ← old chunk, still in corpus
    Budget 2024:     withdrawal cap = RM500      ← new rule

    stale-only corpus → answer says RM1,000 → faithfulness 1.0 → silently wrong

This suite is the missing gate. It asserts `analyst_node` surfaces staleness
(`stale_warning` + per-citation `stale_disclaimer` + `answer_as_of`) and prefers
the newest source on conflict, so a stale-but-faithful answer is flagged and
date-stamped downstream (see synthesiser_node._freshness_instruction) instead of
passing silently.

Runs fully offline (no LLM/RAG calls) — chunks are constructed directly.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.agents.analyst_node import analyst_node
from app.services.vector_store import ChunkResult

# expiry_aware chunk older than analyst_node._STALE_DAYS (90) → stale.
_STALE = (date.today() - timedelta(days=400)).isoformat()
_FRESH = date.today().isoformat()


def _chunk(
    chunk_id: str,
    content: str,
    url: str,
    effective_date: str,
    superseded_by: str | None = None,
) -> ChunkResult:
    return ChunkResult(
        id=chunk_id,
        content=content,
        source_title="KWSP Withdrawal Guidelines",
        source_url=url,
        ministry="KWSP",
        language="en",
        similarity=0.9,
        effective_date=effective_date,
        superseded_by=superseded_by,
    )


@pytest.mark.asyncio
async def test_stale_but_faithful_answer_is_flagged() -> None:
    """The exact failure scenario: only last year's figure is in the corpus
    (the new rule hasn't been ingested). Faithfulness would be 1.0 and the
    citations are real gov.my URLs — the gate must still flag staleness."""
    corpus = [
        _chunk("epf-2023-a", "EPF Budget 2023 withdrawal cap is RM1000.", "https://www.kwsp.gov.my/a", _STALE),
        _chunk("epf-2023-b", "KWSP account 2 withdrawal cap RM1000.", "https://www.kwsp.gov.my/b", _STALE),
    ]

    result = await analyst_node({"query": "epf withdrawal cap", "retrieved_chunks": corpus})

    assert result["stale_warning"] is True, "stale-but-faithful answer passed the gate silently"
    assert result["answer_as_of"] == _STALE
    assert result["citations"], "expected real citations (mirrors the 'looks legit' failure)"
    assert all(c["stale_disclaimer"] for c in result["citations"])
    # Structured, per-chunk staleness record for observability / logging.
    assert result["stale_warnings"], "effective-date staleness not recorded"
    assert all(w["days_since_effective"] > 90 for w in result["stale_warnings"])


@pytest.mark.asyncio
async def test_superseded_chunk_is_never_cited() -> None:
    """When the old figure is explicitly superseded by the new one, the old
    chunk must be hard-rejected — never scored, cited, or passed downstream."""
    corpus = [
        _chunk("epf-2023", "EPF Budget 2023 withdrawal cap is RM1000.", "https://www.kwsp.gov.my/2023", _STALE, superseded_by="epf-2024"),
        _chunk("epf-2024", "EPF Budget 2024 withdrawal cap is RM500.", "https://www.kwsp.gov.my/2024", _FRESH),
    ]

    result = await analyst_node({"query": "epf withdrawal cap", "retrieved_chunks": corpus})

    cited_urls = [c["url"] for c in result["citations"]]
    assert "https://www.kwsp.gov.my/2023" not in cited_urls, "superseded chunk was cited"
    assert [c.id for c in result["retrieved_chunks"]] == ["epf-2024"]
    assert result["stale_warning"] is False


@pytest.mark.asyncio
async def test_prefers_newest_when_old_and_new_both_present() -> None:
    """Transition period: both figures are ingested. The newer source must
    drive the answer (cited first) and no stale warning is raised."""
    corpus = [
        _chunk("epf-2023", "EPF Budget 2023 withdrawal cap is RM1000.", "https://www.kwsp.gov.my/2023", _STALE),
        _chunk("epf-2024", "EPF Budget 2024 withdrawal cap is RM500.", "https://www.kwsp.gov.my/2024", _FRESH),
    ]

    result = await analyst_node({"query": "epf withdrawal cap", "retrieved_chunks": corpus})

    assert result["citations"][0]["url"] == "https://www.kwsp.gov.my/2024", "did not prefer the newest source"
    assert result["stale_warning"] is False


@pytest.mark.asyncio
async def test_fresh_corpus_is_not_flagged() -> None:
    """Baseline: a current corpus must not raise false staleness alarms."""
    corpus = [
        _chunk("epf-a", "EPF withdrawal cap is RM500.", "https://www.kwsp.gov.my/a", _FRESH),
        _chunk("epf-b", "KWSP account 2 withdrawal cap RM500.", "https://www.kwsp.gov.my/b", _FRESH),
    ]

    result = await analyst_node({"query": "epf withdrawal cap", "retrieved_chunks": corpus})

    assert result["stale_warning"] is False
    assert not any(c["stale_disclaimer"] for c in result["citations"])


# ── Validity windows (migration 052) ─────────────────────────────────────────
# The November scenario: the current tax rule runs until 31 Dec, and a new
# policy announced in November takes effect 1 Jan. Both are in the corpus.
_YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
_LAST_YEAR = (date.today() - timedelta(days=120)).isoformat()
_ANNOUNCED = (date.today() - timedelta(days=10)).isoformat()
_NEXT_MONTH = (date.today() + timedelta(days=30)).isoformat()
_IN_WINDOW_END = (date.today() + timedelta(days=29)).isoformat()


def _window_chunk(
    chunk_id: str,
    content: str,
    effective_date: str,
    effective_until: str | None = None,
    announced_date: str | None = None,
) -> ChunkResult:
    return ChunkResult(
        id=chunk_id,
        content=content,
        source_title="LHDN Individual Tax Relief",
        source_url=f"https://www.hasil.gov.my/{chunk_id}",
        ministry="LHDN",
        language="en",
        similarity=0.9,
        effective_date=effective_date,
        effective_until=effective_until,
        announced_date=announced_date,
    )


def _november_corpus() -> list[ChunkResult]:
    return [
        _window_chunk("relief-current-a", "Lifestyle tax relief is RM2,500.", _LAST_YEAR, _IN_WINDOW_END),
        _window_chunk("relief-current-b", "Lifestyle relief cap RM2,500 for this year of assessment.", _LAST_YEAR, _IN_WINDOW_END),
        _window_chunk("relief-next", "Lifestyle tax relief rises to RM3,000.", _NEXT_MONTH, None, _ANNOUNCED),
    ]


@pytest.mark.asyncio
async def test_announced_change_is_not_stated_as_current_rule() -> None:
    """Before 052, prefer-newest ranked the not-yet-effective rule first, so the
    answer stated next year's figure as today's. The current rule must drive
    the answer and citations."""
    result = await analyst_node({"query": "lifestyle tax relief", "domain": "tax", "retrieved_chunks": _november_corpus()})

    cited = [c["url"] for c in result["citations"]]
    assert cited and all("relief-current" in u for u in cited), cited
    assert [c.id for c in result["retrieved_chunks"]] == ["relief-current-a", "relief-current-b"]
    assert result["needs_clarification"] is False
    assert result["stale_warning"] is False


@pytest.mark.asyncio
async def test_announced_change_is_surfaced_with_its_dates() -> None:
    result = await analyst_node({"query": "lifestyle tax relief", "domain": "tax", "retrieved_chunks": _november_corpus()})

    [change] = result["pending_changes"]
    assert change["chunk_id"] == "relief-next"
    assert change["effective_date"] == _NEXT_MONTH
    assert change["announced_date"] == _ANNOUNCED


@pytest.mark.asyncio
async def test_expired_rule_is_never_cited() -> None:
    """After 31 Dec the old rule's window has closed: drop it, answer from the new one."""
    corpus = [
        _window_chunk("relief-old", "Lifestyle tax relief is RM2,500.", _LAST_YEAR, _YESTERDAY),
        _window_chunk("relief-new-a", "Lifestyle tax relief is RM3,000.", _YESTERDAY),
        _window_chunk("relief-new-b", "Lifestyle relief cap RM3,000.", _YESTERDAY),
    ]
    result = await analyst_node({"query": "lifestyle tax relief", "domain": "tax", "retrieved_chunks": corpus})

    assert "https://www.hasil.gov.my/relief-old" not in [c["url"] for c in result["citations"]]
    assert "relief-old" not in [c.id for c in result["retrieved_chunks"]]
    assert result["pending_changes"] == []


@pytest.mark.asyncio
async def test_only_announced_change_in_corpus_is_not_presented_as_current() -> None:
    """The current rule was never ingested: no current evidence, so the answer
    must not go out as confident; the upcoming change is still passed on."""
    corpus = [_window_chunk("relief-next", "Lifestyle tax relief rises to RM3,000.", _NEXT_MONTH, None, _ANNOUNCED)]
    result = await analyst_node({"query": "lifestyle tax relief", "domain": "tax", "retrieved_chunks": corpus})

    assert result["citations"] == []
    assert result["needs_clarification"] is True
    assert [c["chunk_id"] for c in result["pending_changes"]] == ["relief-next"]
