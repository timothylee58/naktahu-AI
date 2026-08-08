"""Warung Watch: crowdsourced live "how busy is it right now" status for
Malaysian warungs/kopitiams/food stalls.

Source model (see 032_warung_watch.sql): `warung_checkins.source` supports
three values, but only 'user_report' is actually written today —

  - 'user_report'            — LIVE. The crowdsourced check-in flow below.
  - 'google_popular_times'   — DEFERRED. fetch_google_popular_times_baseline()
    is a real, documented integration point, but it no-ops unless
    GOOGLE_PLACES_API_KEY is set — this repo has no such key configured, so
    it is never claimed as working. Set the env var to turn it on.
  - 'owner_report'           — DEFERRED, not implemented. A WhatsApp-based
    owner toggle (Meta Cloud API / Twilio) is a separate webhook + phone
    verification flow, out of scope for the crowdsourced-first build.

get_status() aggregates whatever sources exist without caring which one
produced a row, so turning on google_popular_times later needs no schema
or aggregation-query change — just a real API key and a write path.
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from supabase import Client

from core.warung_watch import STALE_WINDOW, aggregate_checkin_status

logger = structlog.get_logger()

_STATUS_WEIGHT = {"empty": 0, "moderate": 1, "packed": 2}


def normalize_name(name: str) -> str:
    """Collapse whitespace/case so "Pelita", " pelita", "PELITA " all match
    the same warung instead of silently creating duplicates."""
    return re.sub(r"\s+", " ", name.strip().lower())


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

    warung = await asyncio.to_thread(_insert)
    logger.info("warung_created", warung_id=warung["id"], name=name)
    return warung


async def search_warungs(
    *, supabase_client: Client, query: str, limit: int = 10
) -> list[dict[str, Any]]:
    normalized = normalize_name(query)
    if not normalized:
        return []

    def _search() -> list[dict[str, Any]]:
        res = (
            supabase_client.table("warungs")
            .select("id,name,location,verified")
            .ilike("normalized_name", f"%{normalized}%")
            .limit(limit)
            .execute()
        )
        return res.data or []

    return await asyncio.to_thread(_search)


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


async def fetch_google_popular_times_baseline(
    *, place_name: str, lat: Optional[float], lng: Optional[float]
) -> Optional[dict[str, Any]]:
    """Deferred integration point for a Google Places "Popular Times"
    baseline layer, to fall back on when there are no fresh crowdsourced
    check-ins. Not wired into get_status() yet, and deliberately a no-op
    unless GOOGLE_PLACES_API_KEY is configured — this repo has no such key
    today, and this function must never be presented as live without one.

    To enable: set GOOGLE_PLACES_API_KEY, implement the Places API "Place
    Details" request (fields=business_status,current_opening_hours or the
    dedicated Popular Times field where available), and write a
    'google_popular_times' row into warung_checkins on a schedule (this is
    historical-pattern data, not truly live, so treat it as a periodic
    background refresh, not a per-request call) — get_status() already
    aggregates by source-agnostic status weight, so no changes are needed
    there once this starts writing real rows.
    """
    if not os.environ.get("GOOGLE_PLACES_API_KEY"):
        logger.info("google_popular_times_skipped_no_api_key", place_name=place_name)
        return None
    raise NotImplementedError(
        "GOOGLE_PLACES_API_KEY is set but the Places API call itself is not "
        "implemented yet — this is a real deferred integration, not a bug."
    )
