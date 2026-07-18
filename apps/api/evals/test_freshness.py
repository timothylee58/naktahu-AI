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
