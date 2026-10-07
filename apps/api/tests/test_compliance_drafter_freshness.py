"""Compliance Drafter freshness: a report must not list a superseded, expired or
not-yet-in-force rule as a current obligation, and must show the dates.

The report is emailed to a business owner as their obligations. Its search path
used to drop every freshness field, so a rule that had been replaced, whose
validity window had closed, or that was only announced (e.g. a Budget measure
tabled but not yet in force) was listed as current, with no date. These tests
use synthetic chunks only: no real rules, businesses or URLs.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.agents import tools
from app.agents.analyst_node import analyst_node
from app.agents.compliance_drafter import nodes
from app.agents.compliance_drafter.nodes import compile_node, query_tax_node
from app.agents.freshness import (
    DEFAULT_STALE_DAYS,
    STRICT_DOMAINS,
    STRICT_STALE_DAYS,
    is_stale,
    partition_by_freshness,
)
from app.services.vector_store import ChunkResult

_EMBEDDING = [0.1] * 1536
_LANGS = ["bm", "en", "zh"]


def _d(offset_days: int) -> str:
    """ISO date relative to today (negative = past)."""
    return (date.today() + timedelta(days=offset_days)).isoformat()


def _chunk(cid: str, **kw: Any) -> ChunkResult:
    base: dict[str, Any] = {
        "id": cid,
        "content": f"Synthetic rule text {cid}.",
        "source_title": f"Fake Source {cid}",
        "source_url": f"https://www.example.gov.my/{cid}",
        "ministry": "Fake Ministry",
        "language": "en",
        "similarity": 0.7,
    }
    base.update(kw)
    return ChunkResult(**base)


def _search(chunks: list[ChunkResult]):
    """Patch the embedder and hybrid_search (autospec: a wrong signature fails)."""
    return (
        patch("app.agents.tools._embed", AsyncMock(return_value=_EMBEDDING)),
        patch("app.agents.tools.hybrid_search", autospec=True, return_value=chunks),
    )


async def _freshness(chunks: list[ChunkResult], domain: str = "tax") -> dict[str, Any]:
    embed, search = _search(chunks)
    with embed, search:
        return await tools.query_rag_freshness("test query", domain, "en")


# ── Shared freshness module ──────────────────────────────────────────────────

def test_partition_splits_current_announced_superseded_expired() -> None:
    chunks = [
        _chunk("undated"),
        _chunk("in-force", effective_date=_d(-30)),
        _chunk("superseded", effective_date=_d(-400), superseded_by="in-force"),
        _chunk("expired", effective_date=_d(-400), effective_until=_d(-1)),
        _chunk("future", effective_date=_d(30), announced_date=_d(-5)),
    ]
    part = partition_by_freshness(chunks)

    assert [c.id for c in part.current] == ["undated", "in-force"]
    assert [c.id for c in part.announced] == ["future"]
    assert [c.id for c in part.superseded] == ["superseded"]
    assert [c.id for c in part.expired] == ["expired"]


def test_partition_precedence_and_boundaries() -> None:
    part = partition_by_freshness([
        # Superseded beats everything, even a future date.
        _chunk("sup-future", effective_date=_d(10), superseded_by="x"),
        # A closed window beats a future start date.
        _chunk("exp-future", effective_date=_d(10), effective_until=_d(-1)),
        # Last day of the window and first day in force are both still current.
        _chunk("until-today", effective_date=_d(-50), effective_until=_d(0)),
        _chunk("starts-today", effective_date=_d(0)),
        # Tomorrow is not yet in force.
        _chunk("starts-tomorrow", effective_date=_d(1)),
    ])

    assert [c.id for c in part.superseded] == ["sup-future"]
    assert [c.id for c in part.expired] == ["exp-future"]
    assert [c.id for c in part.current] == ["until-today", "starts-today"]
    assert [c.id for c in part.announced] == ["starts-tomorrow"]


def test_staleness_windows_are_domain_aware() -> None:
    assert STRICT_STALE_DAYS < DEFAULT_STALE_DAYS and {"tax", "epf"} <= STRICT_DOMAINS
    c = _chunk("old", effective_date=_d(-(STRICT_STALE_DAYS + 20)))
    assert is_stale(c, "tax") and is_stale(c, "epf")
    assert not is_stale(c, "business")  # 365-day window


@pytest.mark.asyncio
async def test_analyst_node_and_partition_agree_on_what_is_in_force() -> None:
    """The point of sharing the logic: both consumers drop and set aside the same rows."""
    chunks = [
        _chunk("in-force", effective_date=_d(-30), content="rule text"),
        _chunk("superseded", superseded_by="in-force", content="rule text"),
        _chunk("expired", effective_until=_d(-1), content="rule text"),
        _chunk("future", effective_date=_d(30), content="rule text"),
    ]
    out = await analyst_node({"query": "rule text", "domain": "tax", "retrieved_chunks": chunks})
    part = partition_by_freshness(chunks)

    assert [c.id for c in out["retrieved_chunks"]] == [c.id for c in part.current]
    assert [p["chunk_id"] for p in out["pending_changes"]] == [c.id for c in part.announced]


# ── Search path ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_superseded_and_expired_chunks_are_dropped_and_counted() -> None:
    out = await _freshness([
        _chunk("ok"),
        _chunk("old-rate", superseded_by="new-rate"),
        _chunk("closed", effective_until=_d(-10)),
        _chunk("closed-too", effective_until=_d(-1)),
    ])

    assert [f["source_title"] for f in out["current"]] == ["Fake Source ok"]
    assert out["announced"] == []
    assert out["dropped"] == {"superseded": 1, "expired": 2, "low_relevance": 0}


@pytest.mark.asyncio
async def test_a_future_dated_chunk_is_announced_never_current() -> None:
    out = await _freshness([
        _chunk("now", effective_date=_d(-10)),
        _chunk("budget-measure", effective_date=_d(90), announced_date=_d(-3)),
    ])

    assert [f["source_title"] for f in out["current"]] == ["Fake Source now"]
    assert [f["source_title"] for f in out["announced"]] == ["Fake Source budget-measure"]
    announced = out["announced"][0]
    assert announced["effective_date"] == _d(90) and announced["announced_date"] == _d(-3)
    assert announced["stale"] is False


@pytest.mark.asyncio
async def test_an_announced_chunk_that_is_also_expired_or_superseded_is_dropped() -> None:
    out = await _freshness([
        _chunk("a", effective_date=_d(30), effective_until=_d(-1)),
        _chunk("b", effective_date=_d(30), superseded_by="a"),
    ])
    assert out["current"] == [] and out["announced"] == []
    assert out["dropped"] == {"superseded": 1, "expired": 1, "low_relevance": 0}


@pytest.mark.asyncio
async def test_announced_changes_are_listed_soonest_first() -> None:
    out = await _freshness([
        _chunk("later", effective_date=_d(200)),
        _chunk("sooner", effective_date=_d(20)),
    ])
    assert [f["effective_date"] for f in out["announced"]] == [_d(20), _d(200)]


@pytest.mark.asyncio
async def test_stale_current_findings_are_flagged_with_their_date() -> None:
    old = _d(-(STRICT_STALE_DAYS + 30))
    out = await _freshness([
        _chunk("old", effective_date=old),
        _chunk("recent", effective_date=_d(-10)),
        _chunk("undated"),
    ], domain="tax")

    by_title = {f["source_title"]: f for f in out["current"]}
    assert by_title["Fake Source old"]["stale"] is True
    assert by_title["Fake Source old"]["stale_ref_date"] == old
    assert by_title["Fake Source recent"]["stale"] is False
    assert by_title["Fake Source recent"]["stale_ref_date"] is None


@pytest.mark.asyncio
async def test_undated_chunks_are_current_and_never_flagged() -> None:
    out = await _freshness([_chunk("undated")], domain="tax")

    (finding,) = out["current"]
    assert finding["stale"] is False
    assert finding["effective_date"] is None and finding["announced_date"] is None
    assert out["dropped"] == {"superseded": 0, "expired": 0, "low_relevance": 0}


@pytest.mark.asyncio
async def test_staleness_window_follows_the_domain() -> None:
    age = _d(-(STRICT_STALE_DAYS + 30))  # between the strict and default windows
    assert (await _freshness([_chunk("x", effective_date=age)], domain="epf"))["current"][0]["stale"] is True
    assert (await _freshness([_chunk("x", effective_date=age)], domain="business"))["current"][0]["stale"] is False


@pytest.mark.asyncio
async def test_expiry_aware_source_date_drives_staleness_only_for_expiry_aware_chunks() -> None:
    old = _d(-(STRICT_STALE_DAYS + 30))
    out = await _freshness([
        _chunk("aware", expiry_aware=True, source_date=old),
        _chunk("plain", expiry_aware=False, source_date=old),
    ])
    by_title = {f["source_title"]: f for f in out["current"]}
    assert by_title["Fake Source aware"]["stale"] is True
    assert by_title["Fake Source plain"]["stale"] is False


@pytest.mark.asyncio
async def test_wider_search_but_bounded_sections() -> None:
    chunks = [_chunk(f"c{i}") for i in range(4)] + [_chunk(f"f{i}", effective_date=_d(10 + i)) for i in range(4)]
    embed, search = _search(chunks)
    with embed, search as hybrid:
        out = await tools.query_rag_freshness("q", "tax")

    hybrid.assert_awaited_once_with("q", _EMBEDDING, domain="tax", limit=tools._FRESHNESS_TOP_K)
    assert len(out["current"]) == 3 and len(out["announced"]) == 3


@pytest.mark.asyncio
async def test_findings_are_json_serialisable() -> None:
    out = await _freshness([_chunk("a", effective_date=_d(-5)), _chunk("b", effective_date=_d(5))])
    assert json.loads(json.dumps(out)) == out


# ── Other agents are unchanged ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_rag_keeps_existing_keys_and_adds_freshness_keys() -> None:
    chunk = _chunk(
        "a", effective_date=_d(-5), effective_until=_d(50), announced_date=_d(-9),
        superseded_by=None, expiry_aware=True, source_date=_d(-6), retrieved_at="2026-01-01T00:00:00Z",
    )
    embed, search = _search([chunk])
    with embed, search:
        (row,) = await tools.query_rag("q", "tax")

    assert {"id", "content", "source_title", "source_url", "ministry", "similarity"} <= row.keys()
    assert (row["id"], row["ministry"], row["similarity"]) == ("a", "Fake Ministry", 0.7)
    assert row["effective_date"] == _d(-5) and row["effective_until"] == _d(50)
    assert row["announced_date"] == _d(-9) and row["superseded_by"] is None
    assert row["expiry_aware"] is True and row["source_date"] == _d(-6)
    assert row["retrieved_at"] == "2026-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_query_rag_findings_output_is_unchanged_and_unfiltered() -> None:
    """immigration, health, research and retrenchment agents call this. It must
    return exactly the old keys, and must NOT start dropping rows for them."""
    chunks = [
        _chunk("a", effective_date=_d(-5)),
        _chunk("old", superseded_by="a"),
        _chunk("future", effective_date=_d(40)),
        _chunk("gone", effective_until=_d(-3)),
    ]
    embed, search = _search(chunks)
    with embed, search:
        findings = await tools.query_rag_findings("q", "immigration")

    assert [f["source_title"] for f in findings] == ["Fake Source a", "Fake Source old", "Fake Source future"]
    for f in findings:
        assert set(f) == {"domain", "summary", "source_title", "source_url", "similarity"}
    assert findings[0] == {
        "domain": "immigration",
        "summary": "Synthetic rule text a.",
        "source_title": "Fake Source a",
        "source_url": "https://www.example.gov.my/a",
        "similarity": 0.7,
    }


# ── Nodes and state ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_node_stores_json_state_and_splits_current_from_announced() -> None:
    chunks = [
        _chunk("now", effective_date=_d(-20)),
        _chunk("next", effective_date=_d(60), announced_date=_d(-2)),
        _chunk("old", superseded_by="now"),
    ]
    embed, search = _search(chunks)
    with embed, search:
        out = await query_tax_node({"domains": ["tax"], "business_type": "sole_proprietor", "language": "en"})

    json.dumps(out)  # no ChunkResult objects in state
    assert [f["source_title"] for f in out["tax_findings"]] == ["Fake Source now"]
    assert [f["source_title"] for f in out["tax_announced"]] == ["Fake Source next"]
    assert out["tax_dropped"] == {"superseded": 1, "expired": 0, "low_relevance": 0}
    assert out["tool_calls"][-1] == {
        "tool": "query_rag", "domain": "tax", "hits": 1, "announced": 1,
        "superseded_dropped": 1, "expired_dropped": 0, "low_relevance_dropped": 0,
    }


@pytest.mark.asyncio
async def test_a_section_the_user_did_not_request_is_not_searched() -> None:
    search = AsyncMock()
    with patch.object(nodes, "query_rag_freshness", search):
        out = await query_tax_node({"domains": ["epf"]})
    search.assert_not_awaited()
    assert out == {"tax_findings": [], "tax_announced": []}


# ── Report rendering ─────────────────────────────────────────────────────────

_CURRENT = {
    "domain": "tax", "summary": "Current rule summary.", "source_title": "Current Source",
    "source_url": "https://www.example.gov.my/current", "similarity": 0.8,
    "effective_date": "2026-01-01", "stale": False, "stale_ref_date": None,
}
_ANNOUNCED = {
    "domain": "tax", "summary": "Announced rule summary.", "source_title": "Announced Source",
    "source_url": "https://www.example.gov.my/announced", "similarity": 0.7,
    "effective_date": "2027-01-01", "announced_date": "2026-10-09", "stale": False, "stale_ref_date": None,
}
_STALE = {
    **_CURRENT, "source_title": "Stale Source", "summary": "Stale rule summary.",
    "effective_date": "2024-02-01", "stale": True, "stale_ref_date": "2024-02-01",
}


async def _report(language: str = "en", **state: Any) -> dict[str, Any]:
    return await compile_node({"language": language, "business_type": "sole_proprietor", **state})


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGS)
async def test_current_findings_show_the_date_they_took_effect(language) -> None:
    html = (await _report(language, domains=["tax"], tax_findings=[_CURRENT]))["report_html"]
    assert nodes._IN_EFFECT_FROM[language].format(date="2026-01-01") in html


@pytest.mark.asyncio
async def test_a_finding_with_no_date_shows_no_date_text() -> None:
    undated = {k: v for k, v in _CURRENT.items() if k not in ("effective_date", "stale", "stale_ref_date")}
    old_shape = {"domain": "tax", "summary": "s", "source_title": "t", "source_url": "", "similarity": 0.1}
    for finding in (undated, old_shape, {**_CURRENT, "effective_date": None}):
        html = (await _report("en", domains=["tax"], tax_findings=[finding]))["report_html"]
        assert "In effect from" not in html and "None" not in html
        assert "outdated" not in html and "<em></em>" not in html


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGS)
async def test_stale_findings_carry_the_outdated_note_with_the_date(language) -> None:
    html = (await _report(language, domains=["tax"], tax_findings=[_STALE, _CURRENT]))["report_html"]
    note = nodes._MAY_BE_OUTDATED[language].format(date="2024-02-01")
    assert html.count(note) == 1  # only on the stale finding
    assert html.index("Stale Source") < html.index(note) < html.index("Current Source")


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGS)
async def test_announced_changes_get_their_own_labelled_sublist(language) -> None:
    out = await _report(language, domains=["tax"], tax_findings=[_CURRENT], tax_announced=[_ANNOUNCED])
    html = out["report_html"]
    heading = f"<h3>{nodes._ANNOUNCED_HEADING[language]}</h3>"

    assert heading in html
    current_part, announced_part = html.split(heading)
    # The future rule is only ever under the announced heading.
    assert "Current Source" in current_part and "Announced Source" not in current_part
    assert "Announced Source" in announced_part and "Current Source" not in announced_part
    assert nodes._TAKES_EFFECT[language].format(date="2027-01-01") in announced_part
    assert nodes._ANNOUNCED_ON[language].format(date="2026-10-09") in announced_part
    # An announced item is never described as already in effect.
    assert "2027-01-01" not in current_part
    assert nodes._IN_EFFECT_FROM[language].format(date="2027-01-01") not in html


@pytest.mark.asyncio
async def test_announced_date_is_omitted_when_unknown() -> None:
    no_announce = {k: v for k, v in _ANNOUNCED.items() if k != "announced_date"}
    html = (await _report("en", domains=["tax"], tax_announced=[no_announce]))["report_html"]
    assert "Takes effect on 2027-01-01" in html and "Announced on" not in html


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGS)
async def test_a_section_with_only_announced_findings_is_not_empty(language) -> None:
    html = (await _report(language, domains=["tax", "epf"], tax_announced=[_ANNOUNCED]))["report_html"]
    # tax has an announced item; only epf (neither current nor announced) is empty.
    assert html.count(nodes._NO_SOURCES[language]) == 1
    assert html.index("Announced Source") < html.index(nodes._NO_SOURCES[language])


@pytest.mark.asyncio
async def test_a_section_with_neither_current_nor_announced_is_empty() -> None:
    out = await _report("en", domains=["tax"], tax_findings=[], tax_announced=[])
    assert nodes._NO_SOURCES["en"] in out["report_html"]
    assert "<h3>" not in out["report_html"] and "<ul></ul>" not in out["report_html"]


@pytest.mark.asyncio
async def test_no_announced_heading_when_nothing_is_announced() -> None:
    html = (await _report("en", domains=["tax"], tax_findings=[_CURRENT]))["report_html"]
    assert "Announced changes" not in html


@pytest.mark.asyncio
async def test_announced_findings_keep_escaping_and_link_rules() -> None:
    evil = {
        **_ANNOUNCED, "source_title": "<img src=x onerror=alert(1)>", "summary": "<script>steal()</script>",
        "effective_date": "<b>2027</b>", "source_url": "javascript:alert(1)",
    }
    html = (await _report("en", domains=["tax"], tax_findings=[{**_CURRENT, "effective_date": "<i>x</i>"}], tax_announced=[evil]))["report_html"]

    for raw in ("<script>", "<img src=x", "<b>2027", "<i>x</i>"):
        assert raw not in html
    assert "&lt;b&gt;2027&lt;/b&gt;" in html
    assert "javascript:" not in html  # a non-web URL is omitted, not linked

    ok = (await _report("en", domains=["tax"], tax_announced=[_ANNOUNCED]))["report_html"]
    assert "<a href='https://www.example.gov.my/announced'>" in ok


@pytest.mark.asyncio
async def test_report_json_sections_carry_current_announced_and_dropped() -> None:
    out = await _report(
        "en", domains=["tax", "epf"], tax_findings=[_CURRENT], tax_announced=[_ANNOUNCED],
        tax_dropped={"superseded": 2, "expired": 1},
    )
    tax, epf = out["report_json"]["sections"]
    assert tax["title"] == "Tax (LHDN)"
    assert tax["current"] == [_CURRENT] and tax["findings"] == [_CURRENT]
    assert tax["announced"] == [_ANNOUNCED]
    assert tax["dropped"] == {"superseded": 2, "expired": 1}
    assert epf["current"] == [] and epf["announced"] == [] and epf["dropped"] == {}
    json.dumps(out["report_json"])
    assert out["report_sections"] == out["report_json"]["sections"]


@pytest.mark.asyncio
async def test_unrequested_domains_stay_out_even_if_state_has_findings() -> None:
    out = await _report("en", domains=["tax"], epf_findings=[_CURRENT], epf_announced=[_ANNOUNCED])
    assert [s["title"] for s in out["report_sections"]] == ["Tax (LHDN)"]
    assert "EPF/KWSP" not in out["report_html"] and "Announced Source" not in out["report_html"]


@pytest.mark.asyncio
async def test_findings_from_before_this_change_still_render() -> None:
    """A checkpointed session carries findings without any date keys."""
    legacy = {"domain": "tax", "summary": "Old shape.", "source_title": "Legacy", "source_url": "https://x.example/l", "similarity": 0.5}
    out = await _report("en", domains=["tax"], tax_findings=[legacy])
    assert "Legacy" in out["report_html"] and out["report_json"]["sections"][0]["announced"] == []
