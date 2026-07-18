"""Tests for app.agents.analyst_node."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.agents.analyst_node import analyst_node
from app.services.vector_store import ChunkResult

_STALE_DATE = (date.today() - timedelta(days=400)).isoformat()
_FRESH_DATE = date.today().isoformat()
_AGED_200 = (date.today() - timedelta(days=200)).isoformat()


def _make_chunk(
    source_url: str = "https://www.hasil.gov.my",
    source_title: str = "LHDN FAQ",
    content: str = "cukai pendapatan individu kadar 2024",
    ministry: str = "LHDN",
    *,
    expiry_aware: bool = False,
    source_date: str | None = None,
    effective_date: str | None = None,
    superseded_by: str | None = None,
    chunk_id: str = "test-id",
) -> ChunkResult:
    return ChunkResult(
        id=chunk_id,
        content=content,
        source_title=source_title,
        source_url=source_url,
        ministry=ministry,
        language="bm",
        similarity=0.8,
        expiry_aware=expiry_aware,
        source_date=source_date,
        effective_date=effective_date,
        superseded_by=superseded_by,
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
    """needs_clarification=True when all chunks score < 0.6."""
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
    assert result["confidence_score"] < 0.6


@pytest.mark.asyncio
async def test_analyst_single_high_scoring_chunk_still_needs_clarification() -> None:
    """A single lucky/keyword-stuffed chunk must not suppress clarification.

    Even though this one chunk scores ≥0.6 on its own (gov.my URL + title +
    full keyword overlap), only 1 chunk clears the 0.3 supporting-chunk bar,
    so the evidentiary gate should force needs_clarification=True.
    """
    good_chunk = _make_chunk(
        source_url="https://www.hasil.gov.my",
        source_title="LHDN FAQ",
        content="cukai pendapatan individu",
    )
    result = await analyst_node({
        "query": "cukai pendapatan individu",
        "retrieved_chunks": [good_chunk],
    })

    assert result["confidence_score"] >= 0.6
    assert result["needs_clarification"] is True


@pytest.mark.asyncio
async def test_analyst_no_clarification_with_multiple_solid_chunks() -> None:
    """needs_clarification=False when ≥2 chunks individually score > 0.3.

    With two (or more) corroborating chunks that each clear the supporting
    bar, the aggregate confidence ≥0.6 should be trusted and clarification
    should not be forced.
    """
    chunk_a = _make_chunk(
        source_url="https://www.hasil.gov.my",
        source_title="LHDN FAQ",
        content="cukai pendapatan individu",
    )
    chunk_b = _make_chunk(
        source_url="https://www.hasil.gov.my/panduan",
        source_title="Panduan Cukai Pendapatan",
        content="cukai pendapatan individu kadar semasa",
    )
    result = await analyst_node({
        "query": "cukai pendapatan individu",
        "retrieved_chunks": [chunk_a, chunk_b],
    })

    assert result["confidence_score"] >= 0.6
    assert result["needs_clarification"] is False


@pytest.mark.asyncio
async def test_analyst_clarification_threshold_is_point_six() -> None:
    """Locks in the actual gate value — the other tests only exercise
    near-0 / near-1 confidence and would pass unchanged at 0.4 or 0.6."""
    from app.agents import analyst_node as analyst_node_module

    assert analyst_node_module._CLARIFICATION_THRESHOLD == 0.6


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
async def test_analyst_flags_stale_evidence() -> None:
    """A stale (expiry_aware, >90d old) top chunk sets stale_warning + answer_as_of
    and marks its citation stale — faithfulness alone would miss this."""
    stale_a = _make_chunk(
        source_url="https://www.kwsp.gov.my/a",
        source_title="KWSP",
        content="epf withdrawal cap rm1000 budget 2023",
        expiry_aware=True,
        source_date=_STALE_DATE,
        chunk_id="a",
    )
    stale_b = _make_chunk(
        source_url="https://www.kwsp.gov.my/b",
        source_title="KWSP FAQ",
        content="epf withdrawal cap rm1000",
        expiry_aware=True,
        source_date=_STALE_DATE,
        chunk_id="b",
    )
    result = await analyst_node({
        "query": "epf withdrawal cap",
        "retrieved_chunks": [stale_a, stale_b],
    })

    assert result["stale_warning"] is True
    assert result["answer_as_of"] == _STALE_DATE
    assert result["citations"] and all(c["stale_disclaimer"] for c in result["citations"])


@pytest.mark.asyncio
async def test_analyst_no_stale_warning_for_fresh_evidence() -> None:
    fresh = _make_chunk(
        source_url="https://www.kwsp.gov.my/a",
        content="epf withdrawal cap rm500",
        expiry_aware=True,
        source_date=_FRESH_DATE,
        chunk_id="a",
    )
    result = await analyst_node({
        "query": "epf withdrawal cap",
        "retrieved_chunks": [fresh],
    })

    assert result["stale_warning"] is False
    assert result["answer_as_of"] is None
    assert not any(c["stale_disclaimer"] for c in result["citations"])


@pytest.mark.asyncio
async def test_analyst_prefers_newest_source_on_conflict() -> None:
    """When last year's and this year's figure both exist, the newer one drives
    the answer (cited first) and no stale warning is raised."""
    old = _make_chunk(
        source_url="https://www.kwsp.gov.my/2023",
        content="epf withdrawal cap rm1000 budget 2023",
        expiry_aware=True,
        source_date=_STALE_DATE,
        chunk_id="old",
    )
    new = _make_chunk(
        source_url="https://www.kwsp.gov.my/2024",
        content="epf withdrawal cap rm500 budget 2024",
        expiry_aware=True,
        source_date=_FRESH_DATE,
        chunk_id="new",
    )
    result = await analyst_node({
        "query": "epf withdrawal cap",
        "retrieved_chunks": [old, new],
    })

    assert result["citations"][0]["url"] == "https://www.kwsp.gov.my/2024"
    assert result["stale_warning"] is False


@pytest.mark.asyncio
async def test_analyst_recency_penalty_lowers_confidence_for_stale() -> None:
    """Identical evidence scores lower when stale than when fresh."""
    def _pair(source_date: str):
        return [
            _make_chunk(
                source_url="https://www.kwsp.gov.my/a",
                content="epf withdrawal cap rm500",
                expiry_aware=True,
                source_date=source_date,
                chunk_id="a",
            ),
            _make_chunk(
                source_url="https://www.kwsp.gov.my/b",
                content="epf withdrawal cap rm500",
                expiry_aware=True,
                source_date=source_date,
                chunk_id="b",
            ),
        ]

    fresh_result = await analyst_node({"query": "epf withdrawal cap", "retrieved_chunks": _pair(_FRESH_DATE)})
    stale_result = await analyst_node({"query": "epf withdrawal cap", "retrieved_chunks": _pair(_STALE_DATE)})

    assert stale_result["confidence_score"] < fresh_result["confidence_score"]


@pytest.mark.asyncio
async def test_analyst_hard_rejects_superseded_chunks() -> None:
    """A chunk with superseded_by set is never scored or cited, and is dropped
    from the retrieved set so the synthesiser can't build context from it."""
    superseded = _make_chunk(
        source_url="https://www.kwsp.gov.my/old",
        content="epf withdrawal cap rm1000",
        superseded_by="new-chunk-id",
        chunk_id="old",
    )
    current = _make_chunk(
        source_url="https://www.kwsp.gov.my/new",
        content="epf withdrawal cap rm500",
        chunk_id="new",
    )
    result = await analyst_node({
        "query": "epf withdrawal cap",
        "retrieved_chunks": [superseded, current],
    })

    urls = [c["url"] for c in result["citations"]]
    assert "https://www.kwsp.gov.my/old" not in urls
    retained_ids = [c.id for c in result["retrieved_chunks"]]
    assert retained_ids == ["new"]


@pytest.mark.asyncio
async def test_analyst_all_superseded_triggers_clarification_and_warning() -> None:
    """If every retrieved chunk is superseded, clarify and flag staleness."""
    superseded = _make_chunk(
        source_url="https://www.kwsp.gov.my/old",
        content="epf withdrawal cap rm1000",
        superseded_by="new-chunk-id",
        chunk_id="old",
    )
    result = await analyst_node({
        "query": "epf withdrawal cap",
        "retrieved_chunks": [superseded],
    })

    assert result["retrieved_chunks"] == []
    assert result["citations"] == []
    assert result["needs_clarification"] is True
    assert result["stale_warning"] is True


@pytest.mark.asyncio
async def test_analyst_effective_date_populates_stale_warnings() -> None:
    """A chunk whose effective_date passed >90d ago is recorded in stale_warnings
    with the expected structure (independent of source_date/expiry_aware)."""
    stale = _make_chunk(
        source_url="https://www.kwsp.gov.my/a",
        source_title="KWSP 2023 Guidelines",
        content="epf withdrawal cap rm1000",
        effective_date=_STALE_DATE,
        chunk_id="epf-2023",
    )
    result = await analyst_node({
        "query": "epf withdrawal cap",
        "retrieved_chunks": [stale],
    })

    assert result["stale_warning"] is True
    assert result["answer_as_of"] == _STALE_DATE
    warnings = result["stale_warnings"]
    assert len(warnings) == 1
    w = warnings[0]
    assert w["chunk_id"] == "epf-2023"
    assert w["source_title"] == "KWSP 2023 Guidelines"
    assert w["effective_date"] == _STALE_DATE
    assert w["days_since_effective"] > 90


@pytest.mark.asyncio
async def test_analyst_staleness_window_is_domain_aware() -> None:
    """A 200-day-old effective_date is stale in a strict policy domain (epf,
    180d) but current in a lenient one (education, 365d)."""
    def _aged():
        return _make_chunk(
            source_url="https://www.gov.my/a",
            content="epf withdrawal cap rm500",
            effective_date=_AGED_200,
            chunk_id="aged",
        )

    strict = await analyst_node({
        "query": "epf withdrawal cap",
        "domain": "epf",
        "retrieved_chunks": [_aged()],
    })
    lenient = await analyst_node({
        "query": "epf withdrawal cap",
        "domain": "education",
        "retrieved_chunks": [_aged()],
    })

    assert strict["stale_warning"] is True
    assert lenient["stale_warning"] is False


@pytest.mark.asyncio
async def test_analyst_future_effective_date_not_stale() -> None:
    """A rule that only takes effect in the future is not flagged as stale."""
    future_date = (date.today() + timedelta(days=30)).isoformat()
    upcoming = _make_chunk(
        source_url="https://www.kwsp.gov.my/a",
        content="epf withdrawal cap rm500",
        effective_date=future_date,
        chunk_id="future",
    )
    result = await analyst_node({
        "query": "epf withdrawal cap",
        "retrieved_chunks": [upcoming],
    })

    assert result["stale_warning"] is False
    assert result["stale_warnings"] == []


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


@pytest.mark.asyncio
async def test_analyst_sets_agency_contact_for_personal_epf_query() -> None:
    result = await analyst_node({
        "query": "What is my EPF balance?",
        "domain": "epf",
        "retrieved_chunks": [],
    })

    assert result["agency_contact"] is not None
    assert result["agency_contact"]["agency"] == "KWSP / EPF"


@pytest.mark.asyncio
async def test_analyst_no_agency_contact_for_general_rules_question() -> None:
    chunk = _make_chunk(content="epf withdrawal age is 55")
    result = await analyst_node({
        "query": "What is the EPF withdrawal age?",
        "domain": "epf",
        "retrieved_chunks": [chunk],
    })

    assert result["agency_contact"] is None
