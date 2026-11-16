"""Unit tests for scripts/retrieval_probe.py (no network, no database)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from scripts import retrieval_probe as probe

_ROUTER = Path(__file__).resolve().parents[1] / "app" / "agents" / "router_node.py"


def test_carries_answer_needs_every_group_and_ignores_case() -> None:
    groups = [["1%"], ["2%", "two percent"]]
    assert probe.carries_answer("Rate is 1% up to 100k, then 2% to 500k", groups)
    assert probe.carries_answer("1% then TWO PERCENT", groups)
    assert not probe.carries_answer("Only 1% is mentioned", groups)
    assert not probe.carries_answer("", groups)
    assert not probe.carries_answer("anything", [])  # no groups means nothing to match, never True


def test_first_rank_is_one_based_and_none_when_absent() -> None:
    rows: list[dict[str, Any]] = [{"content": "nothing"}, {"content": "Spouse relief is RM4,000"}, {"content": "RM4,000"}]
    assert probe.first_rank(rows, [["4,000"]]) == 2
    assert probe.first_rank(rows, [["12,000"]]) is None
    assert probe.first_rank([], [["4,000"]]) is None
    assert probe.first_rank([{"content": None}], [["4,000"]]) is None


def test_search_params_match_the_live_search_and_only_filter_when_asked() -> None:
    plain = probe.search_params("kadar cukai untuk memohon", [0.1], None)
    assert plain["match_count"] == probe.MATCH_COUNT and "domain_filter" not in plain
    assert plain["query_text"] == "kadar cukai untuk memohon" and "keyword_query" in plain  # Malay-affix tsquery
    assert probe.search_params("spouse relief", [0.1], "tax")["domain_filter"] == "tax"


def test_the_default_cases_and_answer_sources_exist_in_the_answer_key() -> None:
    cases = probe.load_cases()
    for case_id in probe.DEFAULT_CASES:
        assert case_id in cases
    for case_id, source_id in probe.ANSWER_SOURCE.items():
        assert case_id in cases and source_id in cases
        assert cases[source_id]["must_contain_groups"], "the source case must state facts a chunk can carry"


def test_router_domains_match_router_node() -> None:
    text = _ROUTER.read_text(encoding="utf-8")
    match = re.search(r"_VALID_DOMAINS\s*=\s*\{([^}]*)\}", text)
    assert match, "router_node._VALID_DOMAINS not found"
    router = set(re.findall(r'"([a-z_]+)"', match.group(1)))
    assert router == set(probe.ROUTER_DOMAINS), "retrieval_probe.ROUTER_DOMAINS drifted from router_node"


class _FakeQuery:
    def __init__(self, rows: list[dict[str, Any]], count: int | None) -> None:
        self._rows, self._count, self.filters = rows, count, []

    def select(self, *a: Any, **k: Any) -> "_FakeQuery":
        return self

    def ilike(self, column: str, pattern: str) -> "_FakeQuery":
        self.filters.append((column, pattern))
        return self

    def limit(self, n: int) -> "_FakeQuery":
        return self

    def execute(self) -> Any:
        from types import SimpleNamespace
        return SimpleNamespace(data=self._rows, count=self._count)


class _FakeSupabase:
    def __init__(self, rows: list[dict[str, Any]], count: int | None = None) -> None:
        self.query = _FakeQuery(rows, count)

    def table(self, name: str) -> _FakeQuery:
        assert name == "document_chunks"
        return self.query


def test_find_phrases_lists_domain_and_total_and_reports_none() -> None:
    rows = [{"source_title": "Stamp Duty Guide", "domain": "property", "source_url": "https://x.gov.my/a",
             "effective_date": None, "effective_until": None}]
    fake = _FakeSupabase(rows, count=12)
    out = "\n".join(probe.find_phrases(fake, ["stamp duty"], limit=8))
    assert "chunks containing 'stamp duty': 12 (showing 8)" in out and "domain=property" in out
    assert fake.query.filters == [("content", "%stamp duty%")]
    assert "(none)" in "\n".join(probe.find_phrases(_FakeSupabase([]), ["nothing here"]))
