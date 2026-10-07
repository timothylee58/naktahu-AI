"""Keyword-layer recall: does hybrid_search's tsquery match the right chunk?

Offline and deterministic — it reproduces Postgres's ``simple`` text config
(lowercase alphanumeric tokens, no stemming) in Python, so it measures only
the keyword half of hybrid_search, not the dense half or live ranking. Each
fixture pairs a query with a chunk that answers it but uses a different
affixed form of the same Malay root ("memohon" vs "permohonan").

Baseline is plainto_tsquery semantics (every query token present). The
expanded query (migration 051 + malay_morph) must match strictly more, and
English queries must not regress.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.malay_morph import build_keyword_tsquery

_FIXTURES = [
    json.loads(line)
    for line in (Path(__file__).parent / "keyword_recall.jsonl").read_text("utf-8").splitlines()
    if line.strip()
]
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tsvector(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _plain_match(query: str, chunk: str) -> bool:
    return _tsvector(query) <= _tsvector(chunk)


def _expanded_match(query: str, chunk: str) -> bool:
    tsq = build_keyword_tsquery(query)
    assert tsq is not None
    doc = _tsvector(chunk)
    groups = [g.strip(" ()").split(" | ") for g in tsq.split(" & ")]
    return all(any(v in doc for v in group) for group in groups)


def _recall(match, language: str | None = None) -> float:
    rows = [f for f in _FIXTURES if language is None or f["language"] == language]
    return sum(match(f["query"], f["chunk"]) for f in rows) / len(rows)


def test_expanded_keyword_recall_beats_plain() -> None:
    plain_bm = _recall(_plain_match, "bm")
    expanded_bm = _recall(_expanded_match, "bm")
    print(f"\nBM keyword recall: plain {plain_bm:.0%} -> expanded {expanded_bm:.0%}")
    assert expanded_bm >= 0.9
    assert expanded_bm > plain_bm


def test_english_keyword_recall_does_not_regress() -> None:
    assert _recall(_expanded_match, "en") >= _recall(_plain_match, "en")


def test_expansion_does_not_match_unrelated_chunks() -> None:
    """Precision guard: a query's expansion must not hit another fixture's chunk
    UNLESS the two share a `topic`. Cross-language synonyms mean a BM query
    legitimately matches an English chunk on the same subject, so same-topic
    fixtures are allowed to overlap; everything else must stay apart."""
    for q in _FIXTURES:
        for other in _FIXTURES:
            if other is q or (q.get("topic") and q.get("topic") == other.get("topic")):
                continue
            assert not _expanded_match(q["query"], other["chunk"]), (q["query"], other["query"])


@pytest.mark.parametrize(
    ("bm_or_en_query", "other_language_chunk"),
    [
        ("pengeluaran KWSP", "Members may make a full EPF withdrawal at the withdrawal age of 55."),
        ("bajet 2027", "Budget 2027 raises the individual income tax relief for lifestyle spending."),
        ("EPF contribution rate", "Kadar caruman KWSP bagi majikan dan pekerja kekal tidak berubah."),
    ],
)
def test_cross_language_synonyms_match_the_same_subject(bm_or_en_query: str, other_language_chunk: str) -> None:
    assert not _plain_match(bm_or_en_query, other_language_chunk)  # the old keyword layer missed these
    assert _expanded_match(bm_or_en_query, other_language_chunk)


def test_every_plain_match_still_matches() -> None:
    for f in _FIXTURES:
        if _plain_match(f["query"], f["chunk"]):
            assert _expanded_match(f["query"], f["chunk"]), f["query"]
