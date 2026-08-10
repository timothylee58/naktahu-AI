"""Warung Watch: crowdsourced live "how busy is it right now" status for
Malaysian warungs/kopitiams/food stalls.

Source model (see 032_warung_watch.sql): `warung_checkins.source` supports
three values, but only 'user_report' is actually written today —

  - 'user_report'            — LIVE. The crowdsourced check-in flow below.
  - 'google_popular_times'   — NOT BUILDABLE. An earlier version of this
    module claimed this was a real deferred integration point behind
    GOOGLE_PLACES_API_KEY. That was wrong: Google's official Places API
    does not expose Popular Times / live-busyness data at all — it's a
    Maps-UI-only feature. The only ways to get it programmatically are
    unofficial scrapers that violate Google's Terms of Service, which
    this repo will not build. The enum value stays (harmless, already
    applied via migration 032 — see CLAUDE.md Trap #5 on not retroactively
    editing applied migrations) but nothing writes to it.
  - 'owner_report'           — DEFERRED, not implemented. A WhatsApp-based
    owner toggle (Meta Cloud API / Twilio) is a separate webhook + phone
    verification flow, out of scope for the crowdsourced-first build.

What IS real and implemented: search_nearby_places() below calls the
official, ToS-compliant Places API (New) Nearby Search endpoint to surface
real nearby place names for the check-in search box — a legitimate,
documented Google API, unlike Popular Times. It's a search assist, not a
check-in source, so it doesn't touch warung_checkins at all.

get_status() aggregates whatever check-in sources exist without caring
which one produced a row — that part of the original design was sound and
is unchanged.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog
from supabase import Client

from core.warung_watch import STALE_WINDOW, aggregate_checkin_status, normalize_name, rank_candidates, select_best_match

logger = structlog.get_logger()

_STATUS_WEIGHT = {"empty": 0, "moderate": 1, "packed": 2}
_PLACES_NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
_PLACES_REQUEST_TIMEOUT = 8.0
# Types that map reasonably onto "warung" — Google's place-type taxonomy has
# no dedicated "warung"/"kopitiam" category. Restaurant/cafe/meal_takeaway
# covers the realistic range without pulling in unrelated results (e.g.
# "grocery_store", which also appears under the broader "food" type).
_NEARBY_PLACE_TYPES = ["restaurant", "cafe", "meal_takeaway"]
# Postgres unique_violation SQLSTATE — raised by warungs_normalized_name_idx
# (a UNIQUE index, see 032_warung_watch.sql) when two concurrent first
# check-ins for the same name race get_or_create_warung's find-then-insert.
_UNIQUE_VIOLATION_CODE = "23505"


async def get_or_create_warung(
    *,
    supabase_client: Client,
    name: str,
    location: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
    created_by: Optional[str],
) -> dict[str, Any]:
    normalized = normalize_name(name)
    if not normalized:
        raise ValueError("Warung name cannot be empty")

    def _find() -> Optional[dict[str, Any]]:
        res = (
            supabase_client.table("warungs")
            .select("*")
            .eq("normalized_name", normalized)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    existing = await asyncio.to_thread(_find)
    if existing:
        return existing

    row = {
        "name": name.strip(),
        "normalized_name": normalized,
        "location": location,
        "lat": lat,
        "lng": lng,
        "created_by": created_by,
    }

    def _insert() -> dict[str, Any]:
        res = supabase_client.table("warungs").insert(row).execute()
        return res.data[0]

    try:
        warung = await asyncio.to_thread(_insert)
    except Exception as exc:
        # Race: another request created this exact normalized_name between
        # our find and our insert. warungs_normalized_name_idx (UNIQUE, see
        # 032_warung_watch.sql) rejects the duplicate — re-fetch and return
        # the winner instead of erroring or leaving two rows to split
        # future reports across.
        if getattr(exc, "code", None) == _UNIQUE_VIOLATION_CODE or _UNIQUE_VIOLATION_CODE in str(exc):
            existing = await asyncio.to_thread(_find)
            if existing:
                logger.info("warung_create_race_resolved", name=name)
                return existing
        raise

    logger.info("warung_created", warung_id=warung["id"], name=name)
    return warung


async def search_warungs(
    *, supabase_client: Client, query: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Autocomplete-style search — returns up to `limit` candidates, ranked
    (exact match, then prefix match, then shortest name) rather than in
    arbitrary DB row order, via core.warung_watch.select_best_match's same
    ranking logic applied across the whole candidate set."""
    normalized = normalize_name(query)
    if not normalized:
        return []

    def _search() -> list[dict[str, Any]]:
        # Fetch a wider pool than `limit` so ranking has something real to
        # sort — DB-side `ilike` order is not meaningful on its own.
        res = (
            supabase_client.table("warungs")
            .select("id,name,location,verified")
            .ilike("normalized_name", f"%{normalized}%")
            .limit(max(limit * 3, 25))
            .execute()
        )
        return res.data or []

    candidates = await asyncio.to_thread(_search)
    return rank_candidates(query, candidates)[:limit]


async def find_best_warung_match(
    *, supabase_client: Client, query: str
) -> Optional[dict[str, Any]]:
    """Single best match for a status lookup — unlike search_warungs (which
    returns several ranked candidates for autocomplete), this picks the one
    warung a status check should resolve to, using the same exact/prefix/
    shortest ranking so "pelita" doesn't arbitrarily resolve to "restoran
    pelita" or vice versa."""
    candidates = await search_warungs(supabase_client=supabase_client, query=query, limit=25)
    return select_best_match(query, candidates)


async def create_checkin(
    *,
    supabase_client: Client,
    warung_id: str,
    status: str,
    reporter_id: Optional[str],
    anon_session_id: Optional[str],
    source: str = "user_report",
) -> dict[str, Any]:
    if status not in _STATUS_WEIGHT:
        raise ValueError(f"Invalid status: {status}")

    row = {
        "warung_id": warung_id,
        "status": status,
        "source": source,
        "reporter_id": reporter_id,
        "anon_session_id": anon_session_id,
    }

    def _insert() -> dict[str, Any]:
        res = supabase_client.table("warung_checkins").insert(row).execute()
        return res.data[0]

    checkin = await asyncio.to_thread(_insert)
    logger.info("warung_checkin_created", warung_id=warung_id, status=status, source=source)
    return checkin


async def get_status(
    *, supabase_client: Client, warung_id: str
) -> dict[str, Any]:
    """Aggregate recent check-ins into a single status. See
    core.warung_watch.aggregate_checkin_status() for the aggregation rules
    (fresh vs stale window, majority-vote math) — this just fetches the
    rows via the sync supabase-py Client this tree uses."""
    stale_cutoff = (datetime.now(timezone.utc) - STALE_WINDOW).isoformat()

    def _fetch() -> list[dict[str, Any]]:
        res = (
            supabase_client.table("warung_checkins")
            .select("status,source,created_at")
            .eq("warung_id", warung_id)
            .gte("created_at", stale_cutoff)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return res.data or []

    rows = await asyncio.to_thread(_fetch)
    return aggregate_checkin_status(rows)


def places_api_configured() -> bool:
    return bool(os.environ.get("GOOGLE_PLACES_API_KEY"))


async def search_nearby_places(
    *, lat: float, lng: float, radius_m: int = 1500, max_results: int = 10
) -> dict[str, Any]:
    """Real nearby-place search via the official Places API (New) Nearby
    Search endpoint — search assist for the check-in box, not a check-in
    source itself. Returns {"configured": False, "places": []} when
    GOOGLE_PLACES_API_KEY isn't set (never claims results it can't produce),
    and degrades the same way — logged, empty list, no exception — on any
    upstream failure, matching how services/speech.py treats an unconfigured
    or failing Google Cloud dependency: this is a convenience layer, and a
    timeout here must not break the rest of the check-in flow.
    """
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return {"configured": False, "places": []}

    body = {
        "includedTypes": _NEARBY_PLACE_TYPES,
        "maxResultCount": max(1, min(max_results, 20)),
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(max(1, min(radius_m, 5000))),
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # Places API (New) requires an explicit field mask on every request —
        # unlike the legacy API, nothing is returned by default.
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location",
    }

    try:
        async with httpx.AsyncClient(timeout=_PLACES_REQUEST_TIMEOUT) as client:
            resp = await client.post(_PLACES_NEARBY_SEARCH_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("places_nearby_search_failed", error=str(exc))
        return {"configured": True, "places": []}

    places = []
    for place in data.get("places", []):
        display_name = place.get("displayName", {}).get("text")
        if not display_name:
            continue
        location = place.get("location") or {}
        places.append({
            "place_id": place.get("id"),
            "name": display_name,
            "address": place.get("formattedAddress"),
            "lat": location.get("latitude"),
            "lng": location.get("longitude"),
        })

    return {"configured": True, "places": places}
