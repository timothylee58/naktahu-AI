"""Deterministic filter-first matching against madani_scheme (migration 037).

Same scoring-first-LLM-second architecture as eligibility_agent's grant
matching: structured eligibility_rules filters run before any LLM call, so
"you qualify for X" is never an LLM guess — it's a real comparison against
a real row's real thresholds. The LLM (synthesiser_node) only explains
matches this node already found; it never invents new ones.

madani_scheme is empty as of migration 037 (no independently-verified
scheme content exists yet — see the migration's own header comment). This
node's empty-table behavior is deliberate and honest: return zero matches
with no_schemes_loaded=True, not a fabricated result. Once real rows exist
(via a verified ingestion pass), this same filter logic starts actually
matching them — no code change needed here for that transition.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.agents.welfare_eligibility_agent.state import MatchedScheme, WelfareProfile, WelfareState

log = structlog.get_logger(__name__)


def _rules_satisfied(rules: dict[str, Any], profile: WelfareProfile) -> tuple[bool, list[str]]:
    """Check one scheme's eligibility_rules against the profile.

    Every key in `rules` is an independent constraint; absent keys impose
    no constraint (a scheme with no income cap in its rules isn't
    income-restricted). Returns (satisfied, reasons) — reasons are only
    populated on a satisfied match, for the LLM step to reference instead
    of re-deriving them.
    """
    reasons: list[str] = []

    max_household = rules.get("max_household_income_myr")
    if max_household is not None:
        income = profile.get("household_monthly_income_myr")
        if income is None or income > max_household:
            return False, []
        reasons.append(f"household income RM{income:,.0f} is within the RM{max_household:,.0f} cap")

    max_individual = rules.get("max_individual_income_myr")
    if max_individual is not None:
        income = profile.get("individual_monthly_income_myr")
        if income is None or income > max_individual:
            return False, []
        reasons.append(f"individual income RM{income:,.0f} is within the RM{max_individual:,.0f} cap")

    states = rules.get("states")
    if states is not None:
        if profile.get("state") not in states:
            return False, []
        reasons.append(f"available in {profile.get('state')}")

    if rules.get("requires_oku") and not profile.get("is_oku"):
        return False, []

    min_children = rules.get("min_dependents_children")
    if min_children is not None and (profile.get("dependents_children") or 0) < min_children:
        return False, []

    min_elderly = rules.get("min_dependents_elderly")
    if min_elderly is not None and (profile.get("dependents_elderly") or 0) < min_elderly:
        return False, []

    employment_statuses = rules.get("employment_status")
    if employment_statuses is not None and profile.get("employment_status") not in employment_statuses:
        return False, []

    housing_types = rules.get("housing_ownership")
    if housing_types is not None and profile.get("housing_ownership") not in housing_types:
        return False, []

    return True, reasons


async def match_node(state: WelfareState, supabase: Any) -> dict[str, Any]:
    profile = state.get("profile") or {}

    if not supabase:
        return {"matched_schemes": [], "no_schemes_loaded": True}

    try:
        res = (
            supabase.table("madani_scheme")
            .select("scheme_name,category,scope,description,implementing_agency,eligibility_rules,source_url,aggregator_url")
            .eq("is_active", True)
            .execute()
        )
        rows = res.data or []
    except Exception as exc:
        log.warning("madani_scheme_fetch_failed", error=str(exc))
        return {"matched_schemes": [], "no_schemes_loaded": True}

    if not rows:
        return {"matched_schemes": [], "no_schemes_loaded": True}

    matched: list[MatchedScheme] = []
    user_state = profile.get("state")
    for row in rows:
        scope = row.get("scope", "federal")
        if scope != "federal" and scope != f"state:{user_state}":
            continue
        rules = row.get("eligibility_rules") or {}
        ok, reasons = _rules_satisfied(rules, profile)
        if not ok:
            continue
        matched.append({
            "scheme_name": row.get("scheme_name", ""),
            "category": row.get("category", ""),
            "scope": scope,
            "description": row.get("description", ""),
            "implementing_agency": row.get("implementing_agency", ""),
            "source_url": row.get("source_url", ""),
            "aggregator_url": row.get("aggregator_url"),
            "match_reasons": reasons,
        })

    return {"matched_schemes": matched, "no_schemes_loaded": False}
