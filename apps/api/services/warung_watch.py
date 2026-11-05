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

from core.warung_watch import (
    STALE_WINDOW,
    aggregate_checkin_status,
    nearby_warungs,
    normalize_name,
    rank_candidates,
    select_best_match,
)

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
            .select("id,name,location,lat,lng,verified")
            .ilike("normalized_name", f"%{normalized}%")
            .limit(max(limit * 3, 25))
            .execute()
        )
        return res.data or []

    candidates = await asyncio.to_thread(_search)
    return rank_candidates(query, candidates)[:limit]


async def list_nearby_warungs(
    *,
    supabase_client: Client,
    lat: float,
    lng: float,
    radius_m: int = 800,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Geotagged warungs inside radius_m, each with its real crowd status.
    Places without coordinates are absent. An empty list means we have no
    located warungs in range — the caller must not fill that with sample rows."""

    def _fetch() -> list[dict[str, Any]]:
        res = (
            supabase_client.table("warungs")
            .select("id,name,location,lat,lng,verified")
            .not_.is_("lat", "null")
            .limit(500)
            .execute()
        )
        return res.data or []

    rows = await asyncio.to_thread(_fetch)
    nearest = nearby_warungs(rows, lat=lat, lng=lng, radius_m=float(radius_m))[: max(1, min(limit, 20))]
    statuses = await get_statuses_bulk(
        supabase_client=supabase_client, warung_ids=[w["id"] for w in nearest]
    )
    return [{"warung": warung, **statuses[warung["id"]]} for warung in nearest]


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
    price_item: Optional[str] = None,
    price_myr: Optional[float] = None,
) -> dict[str, Any]:
    if status not in _STATUS_WEIGHT:
        raise ValueError(f"Invalid status: {status}")
    # Mirrors 033_warung_checkin_price.sql's warung_checkins_price_pair_chk
    # constraint in the application layer too — fail fast with a clear
    # ValueError instead of letting a half-filled pair reach the DB and
    # bounce back as an opaque Postgres constraint-violation error.
    if (price_item is None) != (price_myr is None):
        raise ValueError("price_item and price_myr must both be set or both be None")

    row = {
        "warung_id": warung_id,
        "status": status,
        "source": source,
        "reporter_id": reporter_id,
        "anon_session_id": anon_session_id,
        "price_item": price_item,
        "price_myr": price_myr,
    }

    def _insert() -> dict[str, Any]:
        res = supabase_client.table("warung_checkins").insert(row).execute()
        return res.data[0]

    checkin = await asyncio.to_thread(_insert)
    logger.info(
        "warung_checkin_created",
        warung_id=warung_id,
        status=status,
        source=source,
        has_price=price_myr is not None,
    )
    return checkin


async def get_price_history(
    *, supabase_client: Client, warung_id: str, limit: int = 30
) -> list[dict[str, Any]]:
    """Recent priced check-ins for this warung, oldest-to-newest, for the
    price-trend chart — a real, crowdsourced series (however sparse it
    starts out), never fabricated sample data. Unlike get_status(), this
    intentionally has no staleness cutoff: a trend chart wants the actual
    history, not just what's still "fresh" for a live status badge."""

    def _fetch() -> list[dict[str, Any]]:
        res = (
            supabase_client.table("warung_checkins")
            .select("price_item,price_myr,created_at")
            .eq("warung_id", warung_id)
            .not_.is_("price_myr", "null")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    rows = await asyncio.to_thread(_fetch)
    return list(reversed(rows))


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


# Same per-warung cap get_status() applies, so bulk and single lookups agree.
_ROWS_PER_WARUNG = 50


async def get_statuses_bulk(
    *, supabase_client: Client, warung_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """get_status() for many warungs in ONE query instead of one per id.
    Every requested id is present in the result; ids with no recent
    check-ins get the honest empty aggregate, never a guessed status."""
    ids = list(dict.fromkeys(warung_ids))
    if not ids:
        return {}
    stale_cutoff = (datetime.now(timezone.utc) - STALE_WINDOW).isoformat()

    def _fetch() -> list[dict[str, Any]]:
        res = (
            supabase_client.table("warung_checkins")
            .select("warung_id,status,source,created_at")
            .in_("warung_id", ids)
            .gte("created_at", stale_cutoff)
            .order("created_at", desc=True)
            .limit(len(ids) * _ROWS_PER_WARUNG)
            .execute()
        )
        return res.data or []

    rows = await asyncio.to_thread(_fetch)
    grouped: dict[str, list[dict[str, Any]]] = {warung_id: [] for warung_id in ids}
    for row in rows:
        bucket = grouped.get(row.get("warung_id"))
        # Rows arrive newest-first, so the cap keeps each warung's latest.
        if bucket is not None and len(bucket) < _ROWS_PER_WARUNG:
            bucket.append(row)
    return {warung_id: aggregate_checkin_status(bucket) for warung_id, bucket in grouped.items()}


async def get_statuses_by_name(
    *, supabase_client: Client, names: list[str]
) -> list[dict[str, Any]]:
    """Status for each input name, in input order. Matching is EXACT on
    normalized_name (the table's unique key) — deliberately not the fuzzy
    ranking search uses, because a wrong match here would put another
    warung's crowd level on a place card. Unmatched names get warung=None
    and the empty aggregate."""
    normalized = [normalize_name(name) for name in names]
    wanted = sorted({n for n in normalized if n})
    by_norm: dict[str, dict[str, Any]] = {}
    if wanted:

        def _find() -> list[dict[str, Any]]:
            res = (
                supabase_client.table("warungs")
                .select("id,name,location,lat,lng,verified,normalized_name")
                .in_("normalized_name", wanted)
                .limit(len(wanted))
                .execute()
            )
            return res.data or []

        for row in await asyncio.to_thread(_find):
            by_norm[row["normalized_name"]] = row

    statuses = await get_statuses_bulk(
        supabase_client=supabase_client, warung_ids=[w["id"] for w in by_norm.values()]
    )
    empty = aggregate_checkin_status([])
    results: list[dict[str, Any]] = []
    for name, norm in zip(names, normalized):
        warung = by_norm.get(norm)
        status = statuses[warung["id"]] if warung else empty
        public = {k: v for k, v in warung.items() if k != "normalized_name"} if warung else None
        results.append({"name": name, "warung": public, **status})
    return results


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

        places = []
        # `data.get("places", [])` can legitimately be `None` (the API omits
        # the key or returns it null when zero places match) rather than an
        # absent key, and Places API (New) is a documented but external
        # contract — a malformed/unexpected body (non-dict root, a place
        # entry that isn't a dict) must degrade the same as a network
        # failure below, not 500 the whole check-in flow. Kept inside this
        # try so any of those shapes falls through to the shared handler.
        for place in data.get("places") or []:
            display_name = (place.get("displayName") or {}).get("text")
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
    except Exception as exc:
        logger.warning("places_nearby_search_failed", error=str(exc))
        return {"configured": True, "places": []}

    return {"configured": True, "places": places}
