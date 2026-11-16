"""Tax accuracy eval: does the pipeline give the RIGHT figure, and is it only
confident when it is right?

The existing suites check that the pipeline runs and that retrieval finds
chunks. None of them checks the answer against a known-correct fact, which is how
a confidently wrong SME tax rate reached users. This suite adds an answer key.

- Always runs (no network): the answer key is well formed, and the scorer fails
  the real wrong answer a user was shown (kept below as a regression).
- Live (RUN_LIVE_EVALS=1 + keys): runs every case through the real pipeline and
  reports accuracy plus a confidence-calibration table. The headline safety
  metric is "wrong answers at or above the 0.6 confidence threshold": it must
  be zero, because that is the trust layer's whole job.

Answer-key figures live in tax_accuracy.jsonl with a `key_status`:
- `stable_statutory`: long-standing figures I am confident of but which were NOT
  re-checked against LHDN from the build sandbox (it cannot reach hasil.gov.my).
- `verify_before_use`: year-sensitive figures (SME bands, service tax, digital
  service tax) that must be confirmed against the current official source.
A human should still spot-check the whole key against LHDN/Customs before it
gates anything; a wrong key is worse than no key.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

_EVALS_DIR = Path(__file__).parent
_CONFIDENCE_THRESHOLD = 0.6
_KEY_STATUSES = {"stable_statutory", "verify_before_use"}

# The answer a user was actually shown for the SME question (screenshot, Oct 2026):
# a flat 24% with an invented RM9,000 company relief. Must score as WRONG.
_SME_WRONG_ANSWER = (
    "Di Malaysia, cukai korporat umumnya dikenakan pada kadar tetap 24% untuk syarikat "
    "syarikat di bawah Akta Cukai Pendapatan 1967. Syarikat-syarikat dengan modal bercukai "
    "tidak melebihi RM500,000, dan syarikat-syarikat mulai opsyenan namun belum mencapai "
    "pendapatan RM100,000 setahun, menerima pelepasan cukai korporat maksimum sebanyak RM9,000."
)

_SME_GOOD_ANSWER = (
    "Resident companies are taxed at 24%. An SME (paid-up capital of RM2.5 million or less) "
    "is taxed at 15% on the first RM150,000 and 17% up to RM600,000, then 24% on the balance."
)


def load_cases() -> list[dict[str, Any]]:
    path = _EVALS_DIR / "tax_accuracy.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _contains(text: str, phrase: str) -> bool:
    """Case-insensitive match; a phrase starting or ending in a digit must not be
    part of a longer number, so "1%" does not match "10%" and "30%" not "130%"."""
    phrase = phrase.lower()
    pattern = re.escape(phrase)
    if phrase[0].isdigit():
        pattern = r"(?<![\d,.])" + pattern
    if phrase[-1].isdigit():
        pattern = pattern + r"(?![\d])"
    return re.search(pattern, text) is not None


def score_answer(answer: str, case: dict[str, Any]) -> tuple[bool, list[str]]:
    """Pass only if every required group has at least one of its phrases and no
    forbidden phrase appears. Returns (passed, reasons)."""
    text = answer.lower()
    reasons: list[str] = []
    for group in case.get("must_contain_groups", []):
        if not any(_contains(text, phrase) for phrase in group):
            reasons.append(f"missing one of {group}")
    for phrase in case.get("must_not_contain", []):
        if _contains(text, phrase):
            reasons.append(f"contains forbidden {phrase!r}")
    return (not reasons), reasons


_CASES = load_cases()


def test_answer_key_is_well_formed() -> None:
    ids = [c["id"] for c in _CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    for case in _CASES:
        assert {"id", "query", "key_status", "must_contain_groups", "must_not_contain", "note"} <= case.keys()
        assert case["key_status"] in _KEY_STATUSES
        if not case.get("expect_low_confidence"):
            assert case["must_contain_groups"], f"{case['id']}: an answerable case needs required facts"


def test_the_answer_key_has_thirty_cases_across_both_languages_and_a_decline_set() -> None:
    assert len(_CASES) >= 30
    assert sum(1 for c in _CASES if c.get("expect_low_confidence")) >= 2
    bm_markers = ("apakah", "bilakah", "berapa", "berapakah")
    assert sum(1 for c in _CASES if c["query"].lower().startswith(bm_markers)) >= 5


def test_numbers_are_matched_as_whole_numbers() -> None:
    case = {"must_contain_groups": [["1%"]], "must_not_contain": []}
    assert not score_answer("The rate is 10% on the balance.", case)[0]
    assert score_answer("The rate is 1% on the first RM100,000.", case)[0]
    case = {"must_contain_groups": [["500,000"]], "must_not_contain": []}
    assert not score_answer("The threshold is RM1,500,000.", case)[0]
    assert score_answer("The threshold is RM500,000.", case)[0]


def test_the_answer_users_were_shown_is_scored_wrong() -> None:
    case = next(c for c in _CASES if c["id"] == "sme-rate-en")
    passed, reasons = score_answer(_SME_WRONG_ANSWER, case)
    assert not passed
    assert any("RM9,000" in r or "RM500,000" in r for r in reasons)


def test_a_correct_sme_answer_is_scored_right() -> None:
    case = next(c for c in _CASES if c["id"] == "sme-rate-en")
    assert score_answer(_SME_GOOD_ANSWER, case) == (True, [])


def test_the_company_relief_figure_is_never_attributed_to_companies() -> None:
    case = next(c for c in _CASES if c["id"] == "standard-company-rate")
    assert not score_answer("Companies pay 24% and get a RM9,000 relief.", case)[0]
    assert score_answer("Resident companies pay 24%.", case)[0]


# ── outcome classification ───────────────────────────────────────────────────

OUTCOME_CORRECT = "correct"                    # answered, matches the key, not flagged
OUTCOME_HEDGED_CORRECT = "hedged-correct"      # matches the key, but the pipeline flagged it for follow-up
OUTCOME_FLAGGED_MISS = "flagged-miss"          # no match, and the pipeline itself reported low confidence
OUTCOME_CONFIDENTLY_WRONG = "confidently-wrong"  # no match (or answered an out-of-corpus case) at confidence >= the bar


def classify_outcome(case: dict[str, Any], answer: str, confidence: float, clarified: bool) -> str:
    """What a user would experience, not just whether the key matched.

    The old scorer counted a correct answer the pipeline flagged for follow-up (needs_clarification,
    e.g. a single supporting chunk) as wrong, so the eval measured the evidentiary gate, not the
    answers. A flagged-but-correct answer is reported as its own outcome. Nothing is hidden: strict
    accuracy still counts only OUTCOME_CORRECT, and a wrong answer at or above the 0.6 bar is
    confidently wrong whether or not it was flagged.
    """
    matches = score_answer(answer, case)[0]
    if case.get("expect_low_confidence"):
        declined = clarified or confidence < _CONFIDENCE_THRESHOLD
        if declined and matches:
            return OUTCOME_CORRECT
    elif matches:
        return OUTCOME_HEDGED_CORRECT if clarified else OUTCOME_CORRECT
    return OUTCOME_CONFIDENTLY_WRONG if confidence >= _CONFIDENCE_THRESHOLD else OUTCOME_FLAGGED_MISS


def _case(case_id: str) -> dict[str, Any]:
    return next(c for c in _CASES if c["id"] == case_id)


_EPF_CORRECT = "EPF contributions are limited to RM4,000 and life insurance to RM3,000, RM7,000 in total."


def test_a_correct_answer_that_is_not_flagged_is_correct() -> None:
    assert classify_outcome(_case("epf-relief"), _EPF_CORRECT, 0.8, False) == OUTCOME_CORRECT


def test_a_correct_answer_the_pipeline_flagged_is_hedged_correct_not_wrong() -> None:
    # The EPF answer came back correct at 0.68 with needs_clarification set (one supporting chunk).
    assert classify_outcome(_case("epf-relief"), _EPF_CORRECT, 0.68, True) == OUTCOME_HEDGED_CORRECT


def test_a_wrong_answer_at_or_above_the_bar_is_confidently_wrong_even_when_flagged() -> None:
    wrong = "EPF contributions are limited to RM9,000."
    assert classify_outcome(_case("epf-relief"), wrong, 0.83, False) == OUTCOME_CONFIDENTLY_WRONG
    assert classify_outcome(_case("epf-relief"), wrong, 0.83, True) == OUTCOME_CONFIDENTLY_WRONG


def test_a_miss_the_pipeline_itself_reported_as_low_confidence_is_a_flagged_miss() -> None:
    assert classify_outcome(_case("epf-relief"), "I could not find that.", 0.35, True) == OUTCOME_FLAGGED_MISS


def test_an_out_of_corpus_question_is_correct_only_when_it_is_declined() -> None:
    case = _case("out-of-corpus-singapore")
    decline = "I don't have information on Singapore's corporate tax rate."
    assert classify_outcome(case, decline, 0.35, True) == OUTCOME_CORRECT
    assert classify_outcome(case, decline, 0.75, False) == OUTCOME_CONFIDENTLY_WRONG  # answered at 0.75
    assert classify_outcome(case, "Singapore pays 24%.", 0.35, True) == OUTCOME_FLAGGED_MISS  # declined, but quoted a Malaysian figure


# ── live run ─────────────────────────────────────────────────────────────────

_LIVE = os.environ.get("RUN_LIVE_EVALS") == "1" and (
    bool(os.environ.get("ILMU_API_KEY")) or bool(os.environ.get("ANTHROPIC_API_KEY"))
)


async def _run_pipeline(query: str) -> tuple[str, float, bool]:
    from app.agents.graph import build_graph

    graph = build_graph().compile()
    result = await graph.ainvoke({"query": query, "session_id": "eval-tax", "user_id": None})
    return (
        str(result.get("streaming_token_buffer") or ""),
        float(result.get("confidence_score") or 0.0),
        bool(result.get("needs_clarification")),
    )


@pytest.mark.skipif(not _LIVE, reason="needs RUN_LIVE_EVALS=1 and ILMU_API_KEY/ANTHROPIC_API_KEY")
@pytest.mark.asyncio
async def test_live_accuracy_and_confidence_calibration(capsys: pytest.CaptureFixture[str]) -> None:
    rows: list[dict[str, Any]] = []
    for case in _CASES:
        answer, confidence, clarified = await _run_pipeline(case["query"])
        rows.append({
            "id": case["id"], "status": case["key_status"], "confidence": confidence,
            "outcome": classify_outcome(case, answer, confidence, clarified),
            "answerable": not case.get("expect_low_confidence"), "clarified": clarified,
            "answer": answer, "reasons": score_answer(answer, case)[1],
            "query": case["query"], "note": case.get("note", ""),
        })

    def count(outcome: str, subset: list[dict[str, Any]] | None = None) -> int:
        return sum(1 for r in (rows if subset is None else subset) if r["outcome"] == outcome)

    with capsys.disabled():
        print("\n  id                          key_status                       conf  outcome")
        for r in rows:
            print(f"  {r['id']:<27} {r['status']:<32} {r['confidence']:.2f}  {r['outcome']}")
        for r in rows:
            if r["outcome"] != OUTCOME_CORRECT:
                print(f"\n--- {r['outcome'].upper()}: {r['id']} (confidence {r['confidence']:.2f}, clarified={r['clarified']})")
                print(f"Q: {r['query']}")
                print(f"Why scored: {'; '.join(r['reasons']) or 'matches the key'}")
                print(f"Key note: {r['note']}")
                print(f"A: {r['answer'][:1200]!r}")
        n = len(rows)
        print(f"  accuracy: {count(OUTCOME_CORRECT) / n:.0%} over {n} cases")  # strict: correct and not flagged
        print(
            "  outcomes: "
            f"{count(OUTCOME_CORRECT)} correct, {count(OUTCOME_HEDGED_CORRECT)} hedged-correct, "
            f"{count(OUTCOME_FLAGGED_MISS)} flagged-miss, {count(OUTCOME_CONFIDENTLY_WRONG)} confidently-wrong"
        )
        print(f"  user-visible accuracy (correct + hedged-correct): {(count(OUTCOME_CORRECT) + count(OUTCOME_HEDGED_CORRECT)) / n:.0%}")
        for lo, hi in ((0.0, 0.6), (0.6, 0.8), (0.8, 1.01)):
            bucket = [r for r in rows if lo <= r["confidence"] < hi]
            if bucket:
                print(
                    f"  confidence {lo:.1f}-{min(hi, 1.0):.1f}: {count(OUTCOME_CORRECT, bucket)} correct, "
                    f"{count(OUTCOME_HEDGED_CORRECT, bucket)} hedged-correct of {len(bucket)}"
                )

    # A broken pipeline (no retrieval, LLM down) answers nothing, so nothing is confidently
    # wrong and the check below would pass vacuously. Require that answerable cases were
    # actually answered before trusting the result.
    answerable = [r for r in rows if r["answerable"]]
    answered = [r for r in answerable if r["outcome"] != OUTCOME_FLAGGED_MISS]
    assert len(answered) * 2 >= len(answerable), (
        f"only {len(answered)}/{len(answerable)} answerable cases got an answer: "
        "the pipeline did not run properly (check Supabase/LLM credentials), so this run measures nothing"
    )

    confidently_wrong = [r["id"] for r in rows if r["outcome"] == OUTCOME_CONFIDENTLY_WRONG]
    assert not confidently_wrong, f"wrong answers at confidence >= {_CONFIDENCE_THRESHOLD}: {confidently_wrong}"
