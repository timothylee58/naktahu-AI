"""Investor Intelligence — match a VC/angel investment thesis against the
live Malaysian grant catalogue.

Answers exactly three questions for a given investor profile:

  (a) active_programmes      which grant programmes are currently active in
                             the investor's thesis sectors
  (b) stage_alignment        what startup stage those grants actually target,
                             and where that MISMATCHES the investor's stages
  (c) co_investment_mandates Budget 2026 programmes whose structure requires
                             or rewards a corporate/private co-investor

Composition, not a new agent
────────────────────────────
The three answers above are structured-filter questions over `grant_database`
(sector arrays, is_active, budget_year, grant_type, company_age_min_months),
not open-ended retrieval — a semantic search cannot reliably tell you that a
grant demands 12 months of registration when the investor writes pre-seed
cheques. So the deterministic part is a direct `grant_database` query, in the
same shape as app/agents/eligibility_agent/grant_rag_node.py.

The existing Research Synthesiser (app/agents/research_synthesiser/graph.py)
is REUSED for what it is actually good at: parallel multi-domain RAG fan-out
producing deduplicated, real-URL citations for the narrative context around
those programmes. It is invoked as-is via its compiled graph — no synthesis
logic is duplicated here.

Degradation (Trap #4 / Trap #5): every external call is wrapped. A missing
`grant_database`, a failed RAG fan-out, or a None Supabase client produces an
empty section plus a `degraded` flag — never a crash.

Citations (CLAUDE.md hard rule): URLs come only from grant rows'
`source_url` / `application_url` and from the Research Synthesiser's chunk
metadata. Nothing is constructed or guessed; a programme with no URL simply
carries no citation.
"""
from __future__ import annotations

from typing import Any, Optional

import structlog

log = structlog.get_logger(__name__)

# Canonical startup stages an investor can name. Mirrors the `stage text[]`
# column in migration 022.
VALID_STAGES: tuple[str, ...] = ("pre_seed", "seed", "series_a", "series_b", "growth")

# ── Stage inference heuristic ────────────────────────────────────────────────
# HEURISTIC, NOT PUBLISHED POLICY. `grant_database` has no `target_stage`
# column; the closest hard signal an agency publishes is the minimum company
# age it will accept, so stage is inferred from `company_age_min_months`.
# The bands below are a product judgement about Malaysian grant practice, not
# an agency statement, and every derived claim is labelled as inferred in the
# response so a paying customer never mistakes it for an official rule.
_AGE_BANDS: tuple[tuple[int, int, tuple[str, ...]], ...] = (
    (0, 0, ("pre_seed", "seed")),
    (1, 11, ("pre_seed", "seed")),
    (12, 23, ("seed", "series_a")),
    (24, 10_000, ("series_a", "series_b", "growth")),
)

_STAGE_INFERENCE_BASIS = (
    "Inferred from the programme's minimum company-age requirement "
    "(company_age_min_months); agencies do not publish a startup-stage label. "
    "Verify against the programme guidelines before relying on it."
)

# Signals that a programme expects private/corporate capital alongside it.
_CO_INVESTMENT_GRANT_TYPES = frozenset({"matching", "conditional", "equity"})
_CO_INVESTMENT_KEYWORDS = (
    "co-investment",
    "co investment",
    "coinvestment",
    "co-commitment",
    "co-fund",
    "matching",
    "corporate investor",
    "private investor",
)

_BUDGET_YEAR = 2026


def infer_target_stages(grant: dict[str, Any]) -> tuple[str, ...]:
    """Infer which startup stages a grant programme targets. See _AGE_BANDS."""
    raw = grant.get("company_age_min_months")
    months = int(raw) if isinstance(raw, (int, float)) else 0
    for low, high, stages in _AGE_BANDS:
        if low <= months <= high:
            return stages
    return ()


def _mismatch_reason(grant: dict[str, Any], investor_stages: set[str]) -> Optional[str]:
    """Human-readable mismatch note, or None when the stages align."""
    target = set(infer_target_stages(grant))
    if not investor_stages or not target or (target & investor_stages):
        return None
    months = grant.get("company_age_min_months") or 0
    investor_label = ", ".join(sorted(investor_stages))
    target_label = ", ".join(sorted(target))
    if months:
        return (
            f"You invest at {investor_label}, but {grant.get('programme_name', 'this programme')} "
            f"requires at least {int(months)} months of company registration, which points at "
            f"{target_label} companies. Portfolio companies you back at entry are unlikely to "
            f"qualify until they have been registered that long."
        )
    return (
        f"You invest at {investor_label}, but this programme is aimed at {target_label} companies."
    )


def _co_investment_note(grant: dict[str, Any]) -> Optional[str]:
    """Why this programme looks like a co-investment opportunity, or None."""
    notes = " ".join(
        str(grant.get(k) or "") for k in ("notes_en", "notes_bm")
    ).lower()
    hits = [kw for kw in _CO_INVESTMENT_KEYWORDS if kw in notes]
    grant_type = (grant.get("grant_type") or "").lower()
    if hits:
        return (
            f"Programme notes reference {hits[0]}: "
            f"{(grant.get('notes_en') or grant.get('notes_bm') or '').strip()}"
        )
    if grant_type in _CO_INVESTMENT_GRANT_TYPES:
        return (
            f"Structured as a '{grant_type}' grant, which funds only part of the project cost — "
            "the balance has to come from the company or a co-investor."
        )
    return None


def _citation(grant: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Build a citation from a grant row. Returns None when the row carries no
    real URL — a citation is never fabricated (CLAUDE.md hard rule)."""
    url = grant.get("source_url") or grant.get("application_url")
    if not isinstance(url, str) or not url.startswith("http"):
        return None
    return {
        "title": grant.get("programme_name") or "",
        "ministry": grant.get("agency") or "",
        "url": url,
        "confidence": 1.0,
    }


async def _fetch_active_grants(
    supabase: Any, sectors: list[str]
) -> tuple[list[dict[str, Any]], bool]:
    """Active grant rows whose eligible_sectors overlap `sectors` (or 'all').

    Returns (rows, degraded).
    """
    if supabase is None:
        return [], True
    try:
        conditions = ",".join(
            [f"eligible_sectors.cs.{{{s}}}" for s in sectors] + ["eligible_sectors.cs.{all}"]
        )
        res = await (
            supabase.table("grant_database")
            .select("*")
            .eq("is_active", True)
            .or_(conditions)
            .execute()
        )
        return list(res.data or []), False
    except Exception as exc:
        log.warning("investor_grant_database_unavailable", error=str(exc))
        return [], True


async def _fetch_context_citations(
    thesis: str, sectors: list[str], language: str
) -> list[dict[str, Any]]:
    """Reuse the Research Synthesiser graph for multi-domain RAG citations."""
    query = f"Malaysia government grants {' '.join(sectors)} {thesis}".strip()
    try:
        from app.agents.research_synthesiser.graph import get_research_synthesiser_graph

        graph = get_research_synthesiser_graph()
        result = await graph.ainvoke({"query": query, "language": language})
    except Exception as exc:
        log.warning("investor_research_synthesiser_unavailable", error=str(exc))
        return []

    citations: list[dict[str, Any]] = []
    for citation in (result or {}).get("citations") or []:
        url = citation.get("url")
        if isinstance(url, str) and url.startswith("http"):
            citations.append(citation)
    return citations


def _summarise(grant: dict[str, Any]) -> dict[str, Any]:
    return {
        "programme_name": grant.get("programme_name") or "",
        "agency": grant.get("agency") or "",
        "grant_type": grant.get("grant_type") or "",
        "amount_min_myr": grant.get("amount_min_myr"),
        "amount_max_myr": grant.get("amount_max_myr"),
        "eligible_sectors": list(grant.get("eligible_sectors") or [])[:20],
        "application_deadline": (
            str(grant["application_deadline"]) if grant.get("application_deadline") else None
        ),
        "deadline_is_rolling": bool(grant.get("deadline_is_rolling")),
        "budget_year": grant.get("budget_year"),
        "application_url": grant.get("application_url") or None,
        "source_url": grant.get("source_url") or None,
    }


async def investor_match(
    profile: dict[str, Any],
    supabase: Any,
    *,
    language: str = "en",
) -> dict[str, Any]:
    """Run the three-section investor/grant match for `profile`.

    Never raises on infrastructure failure — an unavailable grant_database or
    RAG layer yields empty sections and `degraded=True`.
    """
    sectors = [s for s in (profile.get("sectors") or []) if isinstance(s, str) and s.strip()]
    investor_stages = {
        s for s in (profile.get("stage") or []) if isinstance(s, str) and s in VALID_STAGES
    }
    thesis = str(profile.get("thesis") or "")

    grants, degraded = await _fetch_active_grants(supabase, sectors)

    # ── (a) active programmes in the thesis sector ───────────────────────────
    active_programmes = [_summarise(g) for g in grants]

    # ── (b) stage alignment, with mismatches flagged ─────────────────────────
    stage_alignment: list[dict[str, Any]] = []
    for grant in grants:
        target = infer_target_stages(grant)
        mismatch = _mismatch_reason(grant, investor_stages)
        stage_alignment.append({
            "programme_name": grant.get("programme_name") or "",
            "target_stages": list(target),
            "company_age_min_months": grant.get("company_age_min_months"),
            "investor_stages": sorted(investor_stages),
            "aligned": mismatch is None,
            "mismatch_reason": mismatch,
            "stage_inference_basis": _STAGE_INFERENCE_BASIS,
        })

    # ── (c) Budget 2026 co-investment mandates ───────────────────────────────
    co_investment_mandates: list[dict[str, Any]] = []
    for grant in grants:
        if grant.get("budget_year") != _BUDGET_YEAR:
            continue
        note = _co_investment_note(grant)
        if not note:
            continue
        ticket_min = profile.get("ticket_size_min_myr")
        ticket_max = profile.get("ticket_size_max_myr")
        amount_min = grant.get("amount_min_myr")
        amount_max = grant.get("amount_max_myr")
        ticket_fit = True
        if ticket_max is not None and amount_min is not None:
            ticket_fit = float(amount_min) <= float(ticket_max)
        if ticket_fit and ticket_min is not None and amount_max is not None:
            ticket_fit = float(amount_max) >= float(ticket_min)
        co_investment_mandates.append({
            **_summarise(grant),
            "co_investment_note": note,
            "matches_co_investment_mandate": bool(profile.get("co_investment_mandate")),
            "ticket_band_overlaps": ticket_fit,
        })

    # ── Citations: grant rows first, then Research Synthesiser context ───────
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for grant in grants:
        cite = _citation(grant)
        if cite and cite["url"] not in seen:
            seen.add(cite["url"])
            citations.append(cite)
    for cite in await _fetch_context_citations(thesis, sectors, language):
        if cite["url"] not in seen:
            seen.add(cite["url"])
            citations.append(cite)

    mismatch_count = sum(1 for s in stage_alignment if not s["aligned"])
    advice: list[str] = []
    if degraded:
        advice.append(
            "The grant catalogue is unavailable, so these results are incomplete. "
            "Retry shortly rather than treating an empty result as 'no matching grants'."
        )
    if not sectors:
        advice.append("No thesis sectors given — only sector-agnostic ('all') programmes can match.")
    if mismatch_count:
        advice.append(
            f"{mismatch_count} of {len(stage_alignment)} programmes look misaligned with your "
            "stated stages. Stage targeting is inferred from minimum company age, not published "
            "by the agencies — confirm before acting on it."
        )
    if profile.get("co_investment_mandate") and not co_investment_mandates:
        advice.append(
            "You have a co-investment mandate but no Budget 2026 co-investment programme matched "
            "your sectors."
        )

    return {
        "active_programmes": active_programmes[:50],
        "stage_alignment": stage_alignment[:50],
        "co_investment_mandates": co_investment_mandates[:50],
        "citations": citations[:20],
        "stage_mismatch_count": mismatch_count,
        "advice": advice[:10],
        "degraded": degraded,
        "language": language,
    }
