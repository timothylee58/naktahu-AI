"""analyst_node — scores each candidate grant against the business profile,
splits results into matched (fully eligible) vs near-miss, and builds the
stacking matrix (conflict pairs, stackable pairs, recommended application
sequence) across the matched grants.

Scoring never fabricates eligibility: every pass/fail check is derived
directly from grant_database fields and the intake-derived business profile.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import structlog

from app.agents.eligibility_agent.compatibility import _load_rules, canonical_name
from app.agents.eligibility_agent.state import EligibilityState
from langchain_core.runnables import RunnableConfig

from app.agents.runtime import supabase_from_config

log = structlog.get_logger(__name__)

# Non-dilutive money first, debt financing last — mirrors how a founder should
# actually sequence applications (grants that don't need repayment or equity
# first, financing facilities that require repayment last).
_TYPE_PRIORITY = {
    "non_dilutive": 0,
    "conditional": 1,
    "matching": 2,
    "reimbursement": 3,
    "equity": 3,
    "financing": 4,
}

_PASSTHROUGH_FIELDS = (
    "programme_name",
    "agency",
    "grant_type",
    "amount_min_myr",
    "amount_max_myr",
    "application_deadline",
    "application_url",
    "processing_weeks_min",
    "processing_weeks_max",
    "stackable_with",
    "conflicts_with",
    "notes_en",
)


def _score_grant(grant: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    ineligibility_reasons: list[str] = []
    hard_fail = False
    near_miss_candidate = False

    total_checks = 0
    passed_checks = 0

    # 1. Deadline
    total_checks += 1
    rolling = bool(grant.get("deadline_is_rolling", False))
    deadline_str = grant.get("application_deadline")
    if rolling:
        passed_checks += 1
        reasons.append("Rolling application window — always open")
    elif deadline_str:
        try:
            deadline = date.fromisoformat(str(deadline_str))
        except ValueError:
            deadline = None
        if deadline is None:
            passed_checks += 1
        else:
            days_left = (deadline - date.today()).days
            if days_left < 0:
                hard_fail = True
                ineligibility_reasons.append(f"Application closed {abs(days_left)} days ago")
            else:
                passed_checks += 1
                reasons.append(f"Application still open, {days_left} days remaining")
    else:
        passed_checks += 1

    # 2. Bumiputera requirement
    total_checks += 1
    if grant.get("bumiputera_required") and not profile.get("is_bumiputera"):
        hard_fail = True
        ineligibility_reasons.append("This grant requires Bumiputera ownership")
    else:
        passed_checks += 1
        if grant.get("bumiputera_required"):
            reasons.append("Bumiputera ownership requirement met")

    # 3. Sector match
    total_checks += 1
    eligible_sectors = grant.get("eligible_sectors") or []
    sector = profile.get("sector", "")
    if eligible_sectors and "all" not in eligible_sectors and sector not in eligible_sectors:
        hard_fail = True
        ineligibility_reasons.append(f"Sector '{sector}' is not in the eligible sectors list")
    else:
        passed_checks += 1
        reasons.append(f"Sector '{sector}' is eligible")

    # 4. Company age (soft — small gaps count as near-miss, not a hard block)
    total_checks += 1
    min_age = grant.get("company_age_min_months") or 0
    age = profile.get("registered_months") or 0
    if age < min_age:
        gap = min_age - age
        ineligibility_reasons.append(
            f"Company must be registered at least {min_age} months (currently {age} months)"
        )
        if gap <= 6:
            near_miss_candidate = True
        else:
            hard_fail = True
    else:
        passed_checks += 1
        reasons.append(f"Company age ({age} months) meets the minimum requirement")

    # 5. Revenue cap (soft — small overages count as near-miss)
    total_checks += 1
    max_rev = grant.get("max_annual_revenue_myr")
    revenue = profile.get("annual_revenue_myr") or 0
    if max_rev is not None and revenue > max_rev:
        gap_pct = (revenue - max_rev) / max_rev if max_rev else 1.0
        ineligibility_reasons.append(
            f"Annual revenue RM{revenue:,.0f} exceeds the cap of RM{max_rev:,.0f}"
        )
        if gap_pct <= 0.2:
            near_miss_candidate = True
        else:
            hard_fail = True
    else:
        passed_checks += 1

    # 6. Conflicts with grants already held
    total_checks += 1
    held = set(profile.get("existing_grants") or [])
    conflicts = set(grant.get("conflicts_with") or [])
    conflicting = held & conflicts
    if conflicting:
        hard_fail = True
        ineligibility_reasons.append(f"Conflicts with already-held grant(s): {', '.join(sorted(conflicting))}")
    else:
        passed_checks += 1

    score = round(passed_checks / total_checks, 2) if total_checks else 0.0
    is_fully_eligible = not hard_fail and not ineligibility_reasons
    is_near_miss = (
        not is_fully_eligible
        and not hard_fail
        and near_miss_candidate
        and len(ineligibility_reasons) <= 1
    )

    result: dict[str, Any] = {field: grant.get(field) for field in _PASSTHROUGH_FIELDS}
    result.update({
        "deadline_is_rolling": rolling,
        "eligibility_score": score,
        "eligibility_reasons": reasons,
        "ineligibility_reasons": ineligibility_reasons,
        "is_fully_eligible": is_fully_eligible,
        "is_near_miss": is_near_miss,
        "chunk_citations": grant.get("chunk_citations", []),
    })
    return result


async def _load_compatibility_rules(
    supabase: Any, names: list[str]
) -> dict[tuple[str, str], dict[str, Any]]:
    """Fetch grant_compatibility_rules rows for `names`, keyed by sorted pair.

    Returns an empty mapping (never raises) when supabase is absent or
    migration 021 has not been applied — the matrix then falls back to the
    binary text[] arrays exactly as before (Trap #4 / Trap #5).
    """
    if supabase is None or len(names) < 2:
        return {}
    rules = await _load_rules(supabase, names)
    if not rules:
        return {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for rule in rules:
        a = canonical_name(rule.get("programme_a", ""))
        b = canonical_name(rule.get("programme_b", ""))
        out[(a, b) if a <= b else (b, a)] = rule
    return out


def _build_stacking_matrix(
    grants: list[dict[str, Any]],
    rules_by_pair: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    names = [g.get("programme_name") for g in grants]
    rules_by_pair = rules_by_pair or {}

    conflict_pairs: list[list[str]] = []
    seen_conflicts: set[tuple[str, str]] = set()
    for g in grants:
        for other in g.get("conflicts_with") or []:
            if other in names:
                pair = tuple(sorted([g.get("programme_name"), other]))
                if pair not in seen_conflicts:
                    seen_conflicts.add(pair)
                    conflict_pairs.append(list(pair))

    stackable_pairs: list[list[str]] = []
    seen_stackable: set[tuple[str, str]] = set()
    for g in grants:
        for other in g.get("stackable_with") or []:
            if other in names:
                pair = tuple(sorted([g.get("programme_name"), other]))
                if pair not in seen_stackable:
                    seen_stackable.add(pair)
                    stackable_pairs.append(list(pair))

    # ── Three-state upgrade: rules-table verdicts override / extend the arrays ──
    # The text[] arrays can only say compatible/incompatible. Where migration
    # 021's rules table has a row for a pair, it is authoritative — including
    # the third state (partial_overlap) the arrays cannot express.
    partial_overlap_pairs: list[dict[str, Any]] = []
    seen_partial: set[tuple[str, str]] = set()
    for rule_key, rule in rules_by_pair.items():
        a, b = rule_key
        if a not in names or b not in names:
            continue
        rule_type = rule.get("rule_type")
        if rule_type == "partial_overlap":
            if rule_key in seen_partial:
                continue
            seen_partial.add(rule_key)
            partial_overlap_pairs.append({
                "pair": [a, b],
                "overlap_scope": rule.get("overlap_scope"),
                "explanation_en": rule.get("explanation_en"),
                "explanation_bm": rule.get("explanation_bm"),
                "source_url": rule.get("source_url"),
            })
            # A partial overlap is not a clean stack — don't also advertise it
            # as stackable if a legacy array claimed so.
            if list(rule_key) in stackable_pairs:
                stackable_pairs.remove(list(rule_key))
        elif rule_type == "conflict" and rule_key not in seen_conflicts:
            seen_conflicts.add(rule_key)
            conflict_pairs.append(list(rule_key))
            if list(rule_key) in stackable_pairs:
                stackable_pairs.remove(list(rule_key))
        elif rule_type == "stackable" and rule_key not in seen_stackable:
            seen_stackable.add(rule_key)
            stackable_pairs.append(list(rule_key))

    ordered = sorted(
        grants,
        key=lambda g: (
            _TYPE_PRIORITY.get(g.get("grant_type"), 99),
            -(g.get("eligibility_score") or 0),
            g.get("processing_weeks_min") or 0,
        ),
    )
    recommended_sequence = [g.get("programme_name") for g in ordered]

    total_min = sum(g.get("amount_min_myr") or 0 for g in grants)
    total_max = sum(g.get("amount_max_myr") or 0 for g in grants)

    # `total_potential_myr_*` keep their original (naive: sum-of-everything)
    # meaning — the synthesiser and /result already read them and existing
    # tests assert on them. `realistic_total_myr_max` is the honest number:
    # walk recommended_sequence and drop any grant that conflicts with one
    # already accepted. Partial overlaps are NOT dropped — both grants can
    # genuinely be held; the restriction is per-expense-line, not per-total,
    # and is surfaced through partial_overlap_pairs instead.
    conflict_lookup: set[tuple[str, str]] = {tuple(p) for p in conflict_pairs}  # type: ignore[misc]
    accepted: list[dict[str, Any]] = []
    excluded: list[str] = []
    for grant in ordered:
        name = grant.get("programme_name")
        clashes = any(
            (min(name, other) if name and other else name, max(name, other) if name and other else other)
            in conflict_lookup
            for other in (g.get("programme_name") for g in accepted)
        )
        if clashes:
            excluded.append(name)
        else:
            accepted.append(grant)
    realistic_total_max = sum(g.get("amount_max_myr") or 0 for g in accepted)

    return {
        "conflict_pairs": conflict_pairs,
        "stackable_pairs": stackable_pairs,
        "partial_overlap_pairs": partial_overlap_pairs,
        "recommended_sequence": recommended_sequence,
        "total_potential_myr_min": total_min,
        "total_potential_myr_max": total_max,
        "realistic_total_myr_max": realistic_total_max,
        "excluded_from_realistic_total": excluded,
    }


async def analyst_node(state: EligibilityState, config: RunnableConfig | None = None) -> dict[str, Any]:
    profile = state.get("business_profile") or {}
    grants = state.get("structured_grants") or []

    scored = [_score_grant(g, profile) for g in grants]
    matched = sorted(
        (g for g in scored if g["is_fully_eligible"]),
        key=lambda g: g["eligibility_score"],
        reverse=True,
    )
    near_miss = sorted(
        (g for g in scored if g["is_near_miss"]),
        key=lambda g: g["eligibility_score"],
        reverse=True,
    )
    stacking_matrix = None
    if matched:
        # Supabase client comes from the run config (never graph state — it
        # isn't checkpoint-serialisable; see app/agents/runtime.py), the same
        # way graph.py threads it into grant_rag_node. Absent client or
        # unapplied migration 021 -> empty rules -> binary-array behaviour.
        rules_by_pair = await _load_compatibility_rules(
            supabase_from_config(config),
            [g.get("programme_name") for g in matched if g.get("programme_name")],
        )
        stacking_matrix = _build_stacking_matrix(matched, rules_by_pair)

    return {
        "matched_grants": matched,
        "near_miss_grants": near_miss,
        "stacking_matrix": stacking_matrix,
    }
