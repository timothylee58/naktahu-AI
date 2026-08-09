"""Pure aggregation logic for Warung Watch check-ins — no Supabase/DB
dependency, so it's safe to import from both the top-level `services/`
tree (routers/warung_watch.py, sync supabase-py Client) and the `app/`
tree (app/agents/warung_watch_node.py, async supabase-py AsyncClient)
without creating a cross-tree coupling between those two otherwise-
separate trees (see CLAUDE.md Trap #1) — only this dependency-free math
is shared, not any client/session state.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# How far back a check-in still counts as "live" before being treated as
# stale background context rather than the headline answer.
FRESH_WINDOW = timedelta(hours=2)
# How far back to look at all before saying "no recent reports."
STALE_WINDOW = timedelta(hours=24)

_STATUS_WEIGHT = {"empty": 0, "moderate": 1, "packed": 2}
_WEIGHT_STATUS = {v: k for k, v in _STATUS_WEIGHT.items()}


def aggregate_checkin_status(
    rows: list[dict[str, Any]], *, now: Optional[datetime] = None
) -> dict[str, Any]:
    """Aggregate warung_checkins rows (each with status/source/created_at,
    already filtered to within STALE_WINDOW by the caller's query) into one
    status.

    Fresh (< FRESH_WINDOW) reports are the headline. If there are none but
    there are reports within STALE_WINDOW, those are surfaced explicitly
    marked stale (is_fresh=False) — never silently presented as current.
    If `rows` is empty, status is None and the caller should say so
    honestly rather than guessing.

    Majority vote is by status weight (empty=0/moderate=1/packed=2),
    average rounded to the nearest defined level — a simple, explainable
    aggregation rather than a black-box model, matching this repo's
    preference for deterministic logic over inferred behavior wherever the
    output feeds directly into what the user is told (analyst_node's
    confidence gate is the same principle applied elsewhere).
    """
    if not rows:
        return {"status": None, "is_fresh": False, "report_count": 0, "last_updated": None, "sources": []}

    now = now or datetime.now(timezone.utc)
    fresh_cutoff = now - FRESH_WINDOW
    fresh_rows = [r for r in rows if datetime.fromisoformat(r["created_at"]) >= fresh_cutoff]
    active_rows = fresh_rows or rows  # fall back to stale rows, but flag is_fresh=False
    is_fresh = bool(fresh_rows)

    avg_weight = sum(_STATUS_WEIGHT[r["status"]] for r in active_rows) / len(active_rows)
    status = _WEIGHT_STATUS[round(avg_weight)]

    return {
        "status": status,
        "is_fresh": is_fresh,
        "report_count": len(active_rows),
        "last_updated": active_rows[0]["created_at"],
        "sources": sorted({r["source"] for r in active_rows}),
    }


def normalize_name(name: str) -> str:
    """Collapse whitespace/case so "Pelita", " pelita", "PELITA " all match
    the same warung instead of silently creating duplicates."""
    return " ".join(name.strip().lower().split())


def _rank_key(normalized_query: str, candidate: dict[str, Any]) -> tuple[int, int]:
    """Sort key: exact normalized match first (tier 0), then names starting
    with the query (tier 1, closest prefix), then everything else (tier 2)
    — ties within a tier broken by shortest name, as a last-resort
    closeness heuristic. Lower sorts first."""
    candidate_normalized = normalize_name(candidate.get("name", ""))
    if candidate_normalized == normalized_query:
        tier = 0
    elif candidate_normalized.startswith(normalized_query):
        tier = 1
    else:
        tier = 2
    return (tier, len(candidate_normalized))


def rank_candidates(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort a substring-search result set by closeness to `query` — see
    _rank_key. A plain `ilike('%query%')` with no ordering returns
    candidates in arbitrary DB row order, which isn't a meaningful
    tiebreaker when multiple names overlap (e.g. "pelita" also matches
    "restoran pelita"). Used by both search_warungs (ranked autocomplete
    list) and select_best_match (its top-1) so the two never disagree on
    what "closest" means."""
    normalized_query = normalize_name(query)
    return sorted(candidates, key=lambda c: _rank_key(normalized_query, c))


def select_best_match(query: str, candidates: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Pick the single best warung match from a substring-search result
    set — the top of rank_candidates(), or None if there are no
    candidates at all."""
    ranked = rank_candidates(query, candidates)
    return ranked[0] if ranked else None
