"""Extracts madani_scheme.eligibility_rules (migration 037's jsonb shape)
from a scraped scheme's free-text title+description via the ILMU chat
model — same LLM-classification pattern as router_node.py's domain
classifier (single-shot chat completion, extract_json_object parsing,
fail-closed to {} on any error).

Why this exists at all: ihsanmadani.gov.my's listing pages don't expose
eligibility as structured data — it's prose inside `description`, if it's
stated at all. WelfareEligibilityAgent's match_node treats every ABSENT
key in eligibility_rules as "no constraint" (see migration 037's header
comment and match_node.py's own docstring), so a naively-loaded scheme
with eligibility_rules={} would silently claim to match every citizen who
asks, income cap or not. That is a worse outcome than no data at all for a
tool citing government welfare eligibility.

This module never on its own decides a scheme is safe to surface. It only
proposes eligibility_rules and a `confident` verdict; the caller
(scripts/ingest_madani.py) is the one that decides whether to flip
needs_review to False, and it only does so when extraction found at least
one concrete constraint (see extract_eligibility_rules's docstring) — an
empty/unconstrained result always leaves needs_review=True for a human to
confirm "genuinely open to all" vs "extraction just found nothing".
"""
from __future__ import annotations

from typing import Any

import structlog

from app.services.llm_client import ILMU_CHAT_MODEL, extract_json_object, ilmu_client

log = structlog.get_logger(__name__)

# Mirrors migration 037's header comment exactly — the one canonical shape
# both match_node.py and this extractor must agree on. Any key not listed
# here is dropped from the parsed result rather than passed through, so a
# hallucinated/misnamed key from the LLM can never silently reach the DB.
_ALLOWED_KEYS = {
    "max_household_income_myr",
    "max_individual_income_myr",
    "states",
    "requires_oku",
    "min_dependents_children",
    "min_dependents_elderly",
    "employment_status",
    "housing_ownership",
}

_STATE_SLUGS = {
    "johor", "kedah", "kelantan", "melaka", "negeri-sembilan", "pahang",
    "perak", "perlis", "pulau-pinang", "sabah", "sarawak", "selangor",
    "terengganu", "kuala-lumpur", "labuan", "putrajaya",
}

_EMPLOYMENT_STATUSES = {"unemployed", "b40", "m40", "t20", "self-employed", "retired", "student"}
_HOUSING_TYPES = {"rented", "owned", "no_fixed_housing"}

_SYSTEM_PROMPT = (
    "You extract structured eligibility criteria from a Malaysian government "
    "welfare/assistance scheme's own title and description text. Return ONLY "
    "a JSON object with these optional keys — include a key ONLY if the "
    "description states it explicitly; OMIT any key you are not confident "
    "about rather than guessing a number or category:\n"
    '  "max_household_income_myr": number — household income ceiling, if stated\n'
    '  "max_individual_income_myr": number — individual income ceiling, if stated\n'
    '  "states": array of lowercase hyphenated Malaysian state/territory slugs '
    "(e.g. \"selangor\", \"kuala-lumpur\") — ONLY if the scheme is explicitly "
    "restricted to specific states; omit for a federal/nationwide scheme\n"
    '  "requires_oku": true — ONLY if the scheme explicitly requires OKU '
    "(disability) registration/status\n"
    '  "min_dependents_children": integer — minimum number of child dependents required, if stated\n'
    '  "min_dependents_elderly": integer — minimum number of elderly dependents required, if stated\n'
    '  "employment_status": array from ["unemployed","b40","m40","t20","self-employed","retired","student"] '
    "— ONLY the categories explicitly named as a requirement\n"
    '  "housing_ownership": array from ["rented","owned","no_fixed_housing"] '
    "— ONLY if housing status is an explicit requirement\n"
    "Never invent a number or category that is not actually present in the text. "
    "A scheme that reads as open to all Malaysians (or all B40/M40 households "
    "without a specific number) should return an empty object {} — do not "
    "fabricate a plausible-looking income figure to fill it in."
)


def _sanitize_rules(raw: dict[str, Any]) -> dict[str, Any]:
    """Keeps only recognized keys with plausible types/values — the same
    defensive parsing app/agents/tools.py's ocr_extract_listing_fields()
    applies to its own LLM-extracted JSON, for the same reason: an LLM
    response is untrusted input, not a validated payload."""
    out: dict[str, Any] = {}

    for key in ("max_household_income_myr", "max_individual_income_myr"):
        val = raw.get(key)
        if isinstance(val, (int, float)) and val >= 0:
            out[key] = float(val)

    states = raw.get("states")
    if isinstance(states, list):
        cleaned = [s for s in states if isinstance(s, str) and s.lower() in _STATE_SLUGS]
        if cleaned:
            out["states"] = sorted({s.lower() for s in cleaned})

    if raw.get("requires_oku") is True:
        out["requires_oku"] = True

    for key in ("min_dependents_children", "min_dependents_elderly"):
        val = raw.get(key)
        if isinstance(val, int) and 0 <= val <= 20:
            out[key] = val

    statuses = raw.get("employment_status")
    if isinstance(statuses, list):
        cleaned = [s for s in statuses if isinstance(s, str) and s.lower() in _EMPLOYMENT_STATUSES]
        if cleaned:
            out["employment_status"] = sorted({s.lower() for s in cleaned})

    housing = raw.get("housing_ownership")
    if isinstance(housing, list):
        cleaned = [h for h in housing if isinstance(h, str) and h.lower() in _HOUSING_TYPES]
        if cleaned:
            out["housing_ownership"] = sorted({h.lower() for h in cleaned})

    # Belt-and-braces: even if a future prompt tweak lets an unrecognized
    # key through, never let it reach the caller.
    return {k: v for k, v in out.items() if k in _ALLOWED_KEYS}


async def extract_eligibility_rules(title: str, description: str) -> tuple[dict[str, Any], bool]:
    """Returns (eligibility_rules, confident).

    confident=True means extraction found at least one concrete,
    recognized constraint — the caller may treat this scheme as reviewed
    (needs_review=False). confident=False covers BOTH "the LLM call
    failed" and "the LLM legitimately found no stated constraints" —
    those two cases are indistinguishable from this function's return
    value alone, and that's deliberate: match_node.py's whole reason for
    needs_review existing is that an empty ruleset must always be treated
    as unconfirmed until something (this function finding a real
    constraint, or a human) actively confirms which case it is. A human
    reviewer reading the scheme description is what upgrades a
    legitimately-open scheme to needs_review=False, not this function
    guessing.
    """
    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Title: {title}\n\nDescription: {description}"},
            ],
            max_tokens=300,
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
    except Exception as exc:
        log.warning("madani_eligibility_extraction_failed", error=str(exc), title=title[:80])
        return {}, False

    parsed = extract_json_object(raw)
    rules = _sanitize_rules(parsed)
    return rules, bool(rules)
