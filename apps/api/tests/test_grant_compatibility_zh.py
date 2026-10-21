"""Mandarin explanations for the grant stacking rules (migration 060).

Two things are covered: the checker picks the zh text and degrades to English when it
is missing (migration not applied yet, or a rule added without a zh row), and the
migration itself covers exactly the rules seeded in migration 021, so adding a rule
later without Mandarin text is caught here instead of shipping an English answer
to a zh user.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from app.agents.eligibility_agent.compatibility import _explanation, grant_compatibility_check
from tests.test_grant_compatibility import MDAG, SDMG, _mock_supabase

MIGRATIONS = Path(__file__).resolve().parents[3] / "infra" / "supabase" / "migrations"
SEED = (MIGRATIONS / "021_grant_compatibility_rules.sql").read_text(encoding="utf-8")
ZH = (MIGRATIONS / "060_grant_compatibility_rules_zh.sql").read_text(encoding="utf-8")

CJK = re.compile(r"[一-鿿]")

# ('A', 'B', 'rule_type'-first-line) rows of the 021 seed: name, name, then the rule type.
_SEED_ROW = re.compile(r"\(\s*'((?:[^']|'')+)',\s*'((?:[^']|'')+)',\s*'(conflict|partial_overlap|stackable)'")
# ('A', 'B', 'zh text') rows of the 060 update.
_ZH_ROW = re.compile(r"\(\s*'((?:[^']|'')+)',\s*'((?:[^']|'')+)',\s*'([^']+)'\s*\)")


def _pair(a: str, b: str) -> frozenset[str]:
    return frozenset((a.replace("''", "'"), b.replace("''", "'")))


def _seed_rules() -> dict[frozenset[str], str]:
    # only the INSERT ... VALUES block: the table's CHECK constraint also lists the rule types
    values = SEED.split("INSERT INTO grant_compatibility_rules", 1)[1].split("ON CONFLICT", 1)[0]
    return {_pair(a, b): kind for a, b, kind in _SEED_ROW.findall(values)}


def _zh_rules() -> dict[frozenset[str], str]:
    return {_pair(a, b): zh for a, b, zh in _ZH_ROW.findall(ZH)}


# ── the checker ──────────────────────────────────────────────────────────────

RULE = {
    "id": "r2", "programme_a": MDAG, "programme_b": SDMG, "rule_type": "partial_overlap",
    "overlap_scope": "same_project_cost", "source_url": "https://www.mdec.my/malaysia-digital/mdag",
    "last_verified": "2026-07-01",
    "explanation_en": "Cannot claim the same project cost under both.",
    "explanation_bm": "Tidak boleh menuntut kos projek yang sama.",
}


def test_explanation_picks_each_language_and_zh_falls_back_to_english_not_malay():
    row: dict[str, Any] = {**RULE, "explanation_zh": "同一项目成本不能重复申领。"}
    assert _explanation(row, "zh") == "同一项目成本不能重复申领。"
    assert _explanation(row, "en") == RULE["explanation_en"]
    assert _explanation(row, "bm") == RULE["explanation_bm"]
    # no zh text (migration 060 not applied -> key absent, or NULL): English, never Malay
    assert _explanation(RULE, "zh") == RULE["explanation_en"]
    assert _explanation({**RULE, "explanation_zh": None}, "zh") == RULE["explanation_en"]
    assert _explanation({"explanation_bm": "hanya BM"}, "zh") == "hanya BM"   # last resort, not empty
    assert _explanation({}, "zh") == ""


@pytest.mark.asyncio
async def test_checker_returns_the_mandarin_explanation_for_a_zh_request():
    sb = _mock_supabase(rules=[{**RULE, "explanation_zh": "同一项目成本不能重复申领。"}], grants=[])
    result = await grant_compatibility_check([MDAG, SDMG], sb, language="zh")
    assert result["language"] == "zh"
    assert result["pairs"][0]["explanation"] == "同一项目成本不能重复申领。"


@pytest.mark.asyncio
async def test_checker_degrades_to_english_when_the_zh_column_is_not_there_yet():
    sb = _mock_supabase(rules=[RULE], grants=[])
    result = await grant_compatibility_check([MDAG, SDMG], sb, language="zh")
    assert result["pairs"][0]["explanation"] == RULE["explanation_en"]


# ── the migration ────────────────────────────────────────────────────────────

def test_the_parsers_see_the_whole_seed():
    assert len(_seed_rules()) == 16 and len(_zh_rules()) == 16   # a regex drift would make the checks below vacuous


def test_migration_060_covers_exactly_the_rules_seeded_in_021():
    seed, zh = _seed_rules(), _zh_rules()
    assert set(zh) == set(seed), (
        f"missing zh for {[sorted(p) for p in set(seed) - set(zh)]}; "
        f"zh rows with no rule {[sorted(p) for p in set(zh) - set(seed)]}"
    )


def test_every_zh_text_is_real_mandarin_not_a_copy_of_the_english():
    for pair, text in _zh_rules().items():
        assert len(CJK.findall(text)) >= 15, f"{sorted(pair)}: too little Chinese: {text!r}"
        assert not text.isascii()


def test_partial_overlap_rows_keep_the_not_a_published_rule_caveat():
    """The English/BM text says these are a conservative policy default, NOT a published
    joint rule. A translation that drops that would present a guess as a citation."""
    seed, zh = _seed_rules(), _zh_rules()
    partial = [pair for pair, kind in seed.items() if kind == "partial_overlap"]
    assert len(partial) == 3
    for pair in partial:
        assert "保守" in zh[pair] and "并非已公布" in zh[pair], f"{sorted(pair)} lost its caveat"


def test_migration_is_idempotent_and_does_not_clobber_hand_edits():
    assert "ADD COLUMN IF NOT EXISTS explanation_zh" in ZH
    assert "r.explanation_zh IS NULL" in ZH
    assert not re.search(r"\bDROP\b|\bDELETE\b|\bTRUNCATE\b", ZH, re.IGNORECASE)
