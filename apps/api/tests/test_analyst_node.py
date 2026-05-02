"""Tests for app.agents.analyst_node."""
from __future__ import annotations

import pytest

from app.agents.analyst_node import analyst_node
from app.services.vector_store import ChunkResult


def _make_chunk(
    source_url: str = "https://www.hasil.gov.my",
    source_title: str = "LHDN FAQ",
    content: str = "cukai pendapatan individu kadar 2024",
    ministry: str = "LHDN",
) -> ChunkResult:
    return ChunkResult(
        id="test-id",
        content=content,
        source_title=source_title,
        source_url=source_url,
        ministry=ministry,
        language="bm",
        similarity=0.8,
    )


@pytest.mark.asyncio
async def test_analyst_scores_gov_url() -> None:
    """Chunks with .gov.my URL score higher than those without."""
    gov_chunk = _make_chunk(source_url="https://www.hasil.gov.my")
    non_gov_chunk = _make_chunk(source_url="https://random-blog.com")

    result = await analyst_node({
        "query": "cukai pendapatan",
        "retrieved_chunks": [gov_chunk, non_gov_chunk],
    })

    assert result["confidence_score"] > 0.0
    citations = result["citations"]
    # gov.my chunk should be first
    assert citations[0]["url"] == "https://www.hasil.gov.my"


@pytest.mark.asyncio
async def test_analyst_needs_clarification_when_low_confidence() -> None:
    """needs_clarification=True when all chunks score < 0.4."""
    low_chunk = _make_chunk(
        source_url="",           # no gov.my → no URL bonus
        source_title="",         # no title → no title bonus
        content="unrelated text about something else entirely",
    )
    result = await analyst_node({
        "query": "zucchini pasta recipe",
        "retrieved_chunks": [low_chunk],
    })

    assert result["needs_clarification"] is True
    assert result["confidence_score"] < 0.4


@pytest.mark.asyncio
async def test_analyst_no_clarification_when_high_confidence() -> None:
    """needs_clarification=False when confidence ≥ 0.4."""
    good_chunk = _make_chunk(
        source_url="https://www.hasil.gov.my",
        source_title="LHDN FAQ",
        content="cukai pendapatan individu",
    )
    result = await analyst_node({
        "query": "cukai pendapatan individu",
        "retrieved_chunks": [good_chunk],
    })

    assert result["confidence_score"] >= 0.4
    assert result["needs_clarification"] is False


@pytest.mark.asyncio
async def test_analyst_empty_chunks_triggers_clarification() -> None:
    """No chunks → confidence=0, needs_clarification=True, empty citations."""
    result = await analyst_node({"query": "anything", "retrieved_chunks": []})

    assert result["needs_clarification"] is True
    assert result["confidence_score"] == 0.0
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_analyst_omits_empty_url_citations() -> None:
    """Citations with empty source_url must be excluded per CLAUDE.md."""
    chunk_no_url = _make_chunk(source_url="")
    chunk_with_url = _make_chunk(source_url="https://www.ssm.com.my")

    result = await analyst_node({
        "query": "daftar syarikat SSM",
        "retrieved_chunks": [chunk_no_url, chunk_with_url],
    })

    urls = [c["url"] for c in result["citations"]]
    assert "" not in urls
    assert "https://www.ssm.com.my" in urls


@pytest.mark.asyncio
async def test_analyst_max_three_citations() -> None:
    """At most 3 citations returned even when more chunks are provided."""
    chunks = [
        _make_chunk(
            source_url=f"https://chunk{i}.gov.my",
            source_title=f"Title {i}",
            content="cukai pendapatan",
        )
        for i in range(5)
    ]
    result = await analyst_node({"query": "cukai pendapatan", "retrieved_chunks": chunks})

    assert len(result["citations"]) <= 3
