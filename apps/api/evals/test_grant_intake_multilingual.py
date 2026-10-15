"""Eligibility Agent intake: does a Mandarin answer yield the same profile as BM/EN?

grant_intake_multilingual.jsonl holds the same six business descriptions in BM,
EN and ZH. The deterministic tests keep that parity honest. The live test runs
the real extractor (Nemotron fast model if configured, else ILMU) and compares
field-level accuracy per language; it is gated like the other live evals because
it calls an LLM.

Gates (live): every language >= 0.85 field accuracy, and ZH within 0.10 of EN,
so a Mandarin regression cannot hide behind good English numbers.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

CASES_PATH = Path(__file__).parent / "grant_intake_multilingual.jsonl"
LANGUAGES = ("bm", "en", "zh")
MIN_ACCURACY = 0.85
MAX_ZH_GAP = 0.10


def load_cases() -> list[dict[str, Any]]:
    return [json.loads(l) for l in CASES_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_every_description_exists_in_all_three_languages():
    groups: dict[str, set[str]] = defaultdict(set)
    for case in load_cases():
        groups[case["group"]].add(case["language"])
    assert groups
    assert all(langs == set(LANGUAGES) for langs in groups.values())


def test_expected_fields_match_across_languages():
    expected: dict[str, list[Any]] = defaultdict(list)
    for case in load_cases():
        expected[case["group"]].append(case["expected"])
    assert all(all(e == exps[0] for e in exps) for exps in expected.values())


def test_mandarin_cases_actually_contain_chinese():
    zh = [c for c in load_cases() if c["language"] == "zh"]
    assert zh and all(any("一" <= ch <= "鿿" for ch in c["text"]) for c in zh)


def _field_matches(want: Any, got: Any) -> bool:
    if isinstance(want, list):
        return isinstance(got, list) and {str(g).lower() for g in got} >= {str(w).lower() for w in want}
    if isinstance(want, str):
        return isinstance(got, str) and got.strip().lower() == want
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        return isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - want) <= max(1, 0.01 * abs(want))
    return got == want


@pytest.mark.skipif(os.environ.get("RUN_LIVE_EVALS") != "1", reason="needs RUN_LIVE_EVALS=1 (calls a live LLM)")
def test_live_intake_accuracy_per_language():
    from app.agents.eligibility_agent.intake_node import _extract_profile_fields

    async def run() -> dict[str, tuple[int, int]]:
        hits: dict[str, list[int]] = {lang: [0, 0] for lang in LANGUAGES}
        for case in load_cases():
            got = await _extract_profile_fields(case["text"], case["language"])
            for field, want in case["expected"].items():
                hits[case["language"]][1] += 1
                hits[case["language"]][0] += int(_field_matches(want, got.get(field)))
        return {k: (v[0], v[1]) for k, v in hits.items()}

    scores = asyncio.run(run())
    acc = {lang: ok / total for lang, (ok, total) in scores.items()}
    print("intake field accuracy:", {k: round(v, 3) for k, v in acc.items()})
    assert all(a >= MIN_ACCURACY for a in acc.values()), acc
    assert acc["en"] - acc["zh"] <= MAX_ZH_GAP, acc
