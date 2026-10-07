"""Eligibility Agent eval gate: does it match grants correctly, state stacking
honestly, and report live deadline checks only when the evidence supports them?

This is a credential-free gate on the agent's own decision logic. It runs the
real code (analyst_node, grant_compatibility_check, verification.assess_results)
over golden cases in grant_agent_cases.jsonl, so a regression in eligibility
rules, stacking verdicts or verification classification fails CI.

What it does and does NOT measure
---------------------------------
- It measures the correctness of the decision logic against labelled fixtures.
- The fixtures are SYNTHETIC programmes ("A", "CIP Spark"...). They test that the
  rules do what we designed them to do; they do not assert anything about what a
  real agency's rules or deadlines currently are. That is the live verification
  step's job, and it is what the faithfulness gate below is about.
- It is NOT answer-faithfulness. Faithfulness (are the generated sentences
  supported by the retrieved chunks) needs an LLM judge and live credentials;
  see scripts/evals/README.md for where that score comes from.

Gates (all deterministic, so thresholds are strict)
---------------------------------------------------
  match precision        1.00  zero false "eligible" results: telling an applicant
                               a grant applies when it does not is the harmful error
  match recall           0.90
  near-miss exactness    0.90
  stacking accuracy      1.00
  unsafe stackable       0     a pair with no evidence must never be "stackable"
  verification accuracy  1.00
  unsafe confirmed       0     never "confirmed" when the evidence does not support it
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock


import app.agents.eligibility_agent.analyst_node as analyst_mod
from app.agents.eligibility_agent.compatibility import grant_compatibility_check
from app.agents.eligibility_agent.verification import assess_results

CASES_PATH = Path(__file__).parent / "grant_agent_cases.jsonl"

MATCH_PRECISION_GATE = 1.0
MATCH_RECALL_GATE = 0.9
NEAR_MISS_EXACT_GATE = 0.9
STACKING_ACCURACY_GATE = 1.0
UNSAFE_STACKABLE_MAX = 0
VERIFICATION_ACCURACY_GATE = 1.0
UNSAFE_CONFIRMED_MAX = 0

_KINDS = {"match", "stacking", "verification"}


def load_cases(kind: str | None = None) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if kind is None or r["kind"] == kind]


# ── matching ─────────────────────────────────────────────────────────────────

def _materialise(grant: dict[str, Any]) -> dict[str, Any]:
    """Resolve the relative `deadline_days` against today so the fixture never ages out."""
    g = dict(grant)
    days = g.pop("deadline_days", None)
    g["application_deadline"] = (date.today() + timedelta(days=days)).isoformat() if days is not None else None
    return g


async def evaluate_matching(cases: list[dict[str, Any]]) -> dict[str, Any]:
    tp = fp = fn = 0
    near_exact = 0
    failures: list[str] = []
    for case in cases:
        state = {
            "business_profile": case["profile"],
            "structured_grants": [_materialise(g) for g in case["grants"]],
        }
        out = await analyst_mod.analyst_node(state)
        matched = {g["programme_name"] for g in out["matched_grants"]}
        near = {g["programme_name"] for g in out["near_miss_grants"]}
        expected = set(case["expected_matched"])
        tp += len(matched & expected)
        fp += len(matched - expected)
        fn += len(expected - matched)
        near_ok = near == set(case["expected_near_miss"])
        near_exact += near_ok
        if matched != expected or not near_ok:
            failures.append(f"{case['id']}: matched={sorted(matched)} near={sorted(near)}")
    return {
        "precision": tp / (tp + fp) if (tp + fp) else 1.0,
        "recall": tp / (tp + fn) if (tp + fn) else 1.0,
        "near_miss_exact": near_exact / len(cases),
        "false_eligible": fp,
        "failures": failures,
    }


# ── stacking ─────────────────────────────────────────────────────────────────

def _mock_supabase(case: dict[str, Any]) -> MagicMock:
    sb = MagicMock()

    def _table(name: str) -> MagicMock:
        chain = MagicMock()
        if name == "grant_compatibility_rules":
            if case["rules_table"] == "missing":
                chain.select.return_value.in_.return_value.execute = AsyncMock(
                    side_effect=Exception('relation "grant_compatibility_rules" does not exist')
                )
            else:
                chain.select.return_value.in_.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=list(case["rules"]))
                )
        else:
            chain.select.return_value.in_.return_value.execute = AsyncMock(
                return_value=MagicMock(data=list(case["grants"]))
            )
        return chain

    sb.table.side_effect = _table
    return sb


async def evaluate_stacking(cases: list[dict[str, Any]]) -> dict[str, Any]:
    correct = unsafe = 0
    failures: list[str] = []
    for case in cases:
        result = await grant_compatibility_check(case["names"], _mock_supabase(case), language="en")
        verdict = result["pairs"][0]["verdict"]
        if verdict == case["expected"]:
            correct += 1
        else:
            failures.append(f"{case['id']}: got {verdict}, expected {case['expected']}")
        if verdict == "stackable" and case["expected"] != "stackable":
            unsafe += 1
    return {"accuracy": correct / len(cases), "unsafe_stackable": unsafe, "failures": failures}


# ── verification ─────────────────────────────────────────────────────────────

def evaluate_verification(cases: list[dict[str, Any]]) -> dict[str, Any]:
    correct = unsafe = 0
    failures: list[str] = []
    for case in cases:
        db = date.fromisoformat(case["db_deadline"]) if case["db_deadline"] else None
        record = assess_results(case["results"], case["host"], db)
        ok = record["status"] == case["expected_status"]
        if case["expected_found_deadline"] is not None:
            ok = ok and record.get("found_deadline") == case["expected_found_deadline"]
        if case["expect_no_evidence"]:
            ok = ok and "evidence" not in record
        correct += ok
        if not ok:
            failures.append(f"{case['id']}: got {record['status']}, expected {case['expected_status']}")
        if record["status"] == "confirmed" and case["expected_status"] != "confirmed":
            unsafe += 1
    return {"accuracy": correct / len(cases), "unsafe_confirmed": unsafe, "failures": failures}


# ── the gates ────────────────────────────────────────────────────────────────

def test_case_file_is_well_formed():
    cases = load_cases()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    assert {c["kind"] for c in cases} == _KINDS
    for kind in _KINDS:
        assert len(load_cases(kind)) >= 8, f"too few {kind} cases to gate on"


async def test_matching_gate():
    m = await evaluate_matching(load_cases("match"))
    print(f"\nmatch: precision={m['precision']:.3f} recall={m['recall']:.3f} near_miss_exact={m['near_miss_exact']:.3f}")
    assert m["false_eligible"] == 0, f"false eligible results: {m['failures']}"
    assert m["precision"] >= MATCH_PRECISION_GATE, m["failures"]
    assert m["recall"] >= MATCH_RECALL_GATE, m["failures"]
    assert m["near_miss_exact"] >= NEAR_MISS_EXACT_GATE, m["failures"]


async def test_stacking_gate():
    s = await evaluate_stacking(load_cases("stacking"))
    print(f"\nstacking: accuracy={s['accuracy']:.3f} unsafe_stackable={s['unsafe_stackable']}")
    assert s["unsafe_stackable"] <= UNSAFE_STACKABLE_MAX, s["failures"]
    assert s["accuracy"] >= STACKING_ACCURACY_GATE, s["failures"]


def test_verification_gate():
    v = evaluate_verification(load_cases("verification"))
    print(f"\nverification: accuracy={v['accuracy']:.3f} unsafe_confirmed={v['unsafe_confirmed']}")
    assert v["unsafe_confirmed"] <= UNSAFE_CONFIRMED_MAX, v["failures"]
    assert v["accuracy"] >= VERIFICATION_ACCURACY_GATE, v["failures"]


# ── the gate must actually be able to fail ───────────────────────────────────

async def test_matching_gate_catches_a_scorer_that_ignores_the_bumiputera_rule(monkeypatch):
    """If the Bumiputera check is dropped, false-eligible results must trip the gate."""
    real = analyst_mod._score_grant

    def broken(grant: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        return real({**grant, "bumiputera_required": False}, profile)

    monkeypatch.setattr(analyst_mod, "_score_grant", broken)
    m = await evaluate_matching(load_cases("match"))
    assert m["false_eligible"] > 0 and m["precision"] < MATCH_PRECISION_GATE


async def test_stacking_gate_catches_unknown_defaulting_to_stackable(monkeypatch):
    """If an unverified pair were reported stackable, the safety counter must see it."""
    import app.agents.eligibility_agent.compatibility as comp

    monkeypatch.setattr(comp, "_legacy_verdict", lambda *a, **k: (comp.STACKABLE, None))
    s = await evaluate_stacking(load_cases("stacking"))
    assert s["unsafe_stackable"] > 0


def test_verification_gate_catches_a_classifier_that_trusts_any_domain(monkeypatch):
    import app.agents.eligibility_agent.verification as ver

    monkeypatch.setattr(ver, "_same_site", lambda url, host: True)
    v = evaluate_verification(load_cases("verification"))
    assert v["unsafe_confirmed"] > 0 or v["accuracy"] < VERIFICATION_ACCURACY_GATE
