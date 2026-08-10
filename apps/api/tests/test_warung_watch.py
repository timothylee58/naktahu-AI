"""Warung Watch: router auth/validation/degraded-mode boundaries, plus
direct unit coverage of get_status()'s aggregation math — the "trust
layer" for this feature (equivalent to analyst_node's confidence check
elsewhere in this repo), since that's what stops a single stale or
mismatched report from being presented as current fact.
"""
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter
from core.warung_watch import rank_candidates, select_best_match
from services.warung_watch import (
    find_best_warung_match,
    get_or_create_warung,
    get_status,
    normalize_name,
    search_nearby_places,
    search_warungs,
)


def _auth_header(sub: str = "warung-user") -> dict[str, str]:
    tok = jwt.encode(
        {"sub": sub, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)

    warung_row = {"id": "warung-1", "name": "Pelita", "location": None, "verified": False}
    checkin_row = {"id": "checkin-1", "warung_id": "warung-1", "status": "packed", "source": "user_report"}

    warungs_table = MagicMock()
    warungs_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    warungs_table.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[warung_row])
    warungs_table.insert.return_value.execute.return_value = MagicMock(data=[warung_row])

    checkins_table = MagicMock()
    checkins_table.insert.return_value.execute.return_value = MagicMock(data=[checkin_row])
    checkins_table.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

    def _table(name):
        # Startup lifespan probes an unrelated table (user_sessions) to
        # check Supabase connectivity — fall back to a generic mock for
        # anything other than the two tables this router actually touches,
        # so that probe doesn't KeyError and force degraded (None) mode.
        return {"warungs": warungs_table, "warung_checkins": checkins_table}.get(name, MagicMock())

    sb = MagicMock()
    sb.table.side_effect = _table
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, sb, warungs_table, checkins_table


def _checkin_body(**overrides):
    body = {"name": "Pelita", "status": "packed"}
    body.update(overrides)
    return body


# ── router: happy path ──────────────────────────────────────────────────

def test_checkin_anonymous_allowed(client):
    c, sb, warungs_table, checkins_table = client
    res = c.post("/api/v1/warung-watch/checkin", json=_checkin_body())
    assert res.status_code == 201, res.text
    inserted_warung = warungs_table.insert.call_args[0][0]
    assert inserted_warung["created_by"] is None
    inserted_checkin = checkins_table.insert.call_args[0][0]
    assert inserted_checkin["reporter_id"] is None
    assert inserted_checkin["status"] == "packed"


def test_checkin_authenticated_records_user_id(client):
    c, sb, warungs_table, checkins_table = client
    res = c.post("/api/v1/warung-watch/checkin", json=_checkin_body(), headers=_auth_header(sub="warung-user"))
    assert res.status_code == 201, res.text
    inserted_warung = warungs_table.insert.call_args[0][0]
    assert inserted_warung["created_by"] == "warung-user"
    inserted_checkin = checkins_table.insert.call_args[0][0]
    assert inserted_checkin["reporter_id"] == "warung-user"


def test_checkin_reuses_existing_warung(client):
    c, sb, warungs_table, checkins_table = client
    warungs_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "warung-1", "name": "Pelita", "location": None, "verified": False}]
    )
    res = c.post("/api/v1/warung-watch/checkin", json=_checkin_body())
    assert res.status_code == 201, res.text
    warungs_table.insert.assert_not_called()


def test_search_returns_matches(client):
    c, *_ = client
    res = c.get("/api/v1/warung-watch/search", params={"q": "peli"})
    assert res.status_code == 200, res.text
    assert res.json()[0]["name"] == "Pelita"


def test_search_endpoint_ranks_exact_match_first_among_overlapping_names(client):
    """Regression coverage at the HTTP layer (not just find_best_warung_match):
    /search must return ranked results too, since the frontend's autocomplete
    list (warung-watch/page.tsx's suggestion dropdown) shows results[0]
    first without re-ranking client-side. Ranking tiers: exact match (0) >
    prefix match (1) > substring-only match (2), ties broken by shortest
    name — "Restoran Pelita" doesn't start with "pelita" so it's tier 2
    despite being shorter than "Pelita Corner Cafe" (tier 1, a real
    prefix)."""
    c, sb, warungs_table, checkins_table = client
    warungs_table.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {"id": "warung-3", "name": "Restoran Pelita", "location": None, "verified": False},
            {"id": "warung-2", "name": "Pelita Corner Cafe", "location": None, "verified": False},
            {"id": "warung-1", "name": "Pelita", "location": None, "verified": False},
        ]
    )
    res = c.get("/api/v1/warung-watch/search", params={"q": "Pelita"})
    assert res.status_code == 200, res.text
    names = [r["name"] for r in res.json()]
    assert names == ["Pelita", "Pelita Corner Cafe", "Restoran Pelita"]


def test_status_no_matching_warung(client):
    c, sb, warungs_table, checkins_table = client
    warungs_table.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    res = c.get("/api/v1/warung-watch/status", params={"name": "Nonexistent"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] is None


def test_status_prefers_exact_match_over_substring_match(client):
    """Regression test: searching "Pelita" with both "Pelita" and "Restoran
    Pelita" among the candidates must resolve to the exact match — a bare
    substring search with no ranking previously returned an arbitrary row."""
    c, sb, warungs_table, checkins_table = client
    warungs_table.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {"id": "warung-2", "name": "Restoran Pelita", "location": None, "verified": False},
            {"id": "warung-1", "name": "Pelita", "location": None, "verified": False},
        ]
    )
    res = c.get("/api/v1/warung-watch/status", params={"name": "Pelita"})
    assert res.status_code == 200, res.text
    assert res.json()["warung"]["name"] == "Pelita"


# ── validation ───────────────────────────────────────────────────────────

def test_checkin_rejects_invalid_status(client):
    c, *_ = client
    res = c.post("/api/v1/warung-watch/checkin", json=_checkin_body(status="on-fire"))
    assert res.status_code == 422


def test_checkin_rejects_empty_name(client):
    c, *_ = client
    res = c.post("/api/v1/warung-watch/checkin", json=_checkin_body(name=""))
    assert res.status_code == 422


def test_checkin_rejects_oversized_name(client):
    c, *_ = client
    res = c.post("/api/v1/warung-watch/checkin", json=_checkin_body(name="x" * 201))
    assert res.status_code == 422


def test_checkin_rejects_out_of_range_lat(client):
    c, *_ = client
    res = c.post("/api/v1/warung-watch/checkin", json=_checkin_body(lat=999))
    assert res.status_code == 422


# ── degraded mode ────────────────────────────────────────────────────────

def test_checkin_503_when_supabase_unavailable(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.post("/api/v1/warung-watch/checkin", json=_checkin_body())
    assert res.status_code == 503


def test_status_503_when_supabase_unavailable(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.get("/api/v1/warung-watch/status", params={"name": "Pelita"})
    assert res.status_code == 503


def test_search_503_when_supabase_unavailable(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.get("/api/v1/warung-watch/search", params={"q": "peli"})
    assert res.status_code == 503


# ── rate limit boundary (shared apply_query_rate_limit: 30/hour anon) ────

def test_checkin_rate_limit_31st_anonymous_returns_429(client):
    c, *_ = client
    for i in range(30):
        r = c.post("/api/v1/warung-watch/checkin", json=_checkin_body(name=f"Pelita {i}"))
        assert r.status_code == 201, r.text
    blocked = c.post("/api/v1/warung-watch/checkin", json=_checkin_body(name="Pelita blocked"))
    assert blocked.status_code == 429


# ── normalize_name ───────────────────────────────────────────────────────

def test_normalize_name_folds_case_and_whitespace():
    assert normalize_name("  Pelita  ") == "pelita"
    assert normalize_name("PELITA") == "pelita"
    assert normalize_name("Restoran   Pelita") == "restoran pelita"


# ── get_status aggregation (the trust layer) ─────────────────────────────

def _row(status: str, minutes_ago: int, source: str = "user_report") -> dict:
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {"status": status, "source": source, "created_at": ts.isoformat()}


@pytest.mark.asyncio
async def test_get_status_no_reports_returns_none():
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    result = await get_status(supabase_client=sb, warung_id="w1")
    assert result["status"] is None
    assert result["is_fresh"] is False
    assert result["report_count"] == 0


@pytest.mark.asyncio
async def test_get_status_majority_vote_among_fresh_reports():
    sb = MagicMock()
    rows = [_row("packed", 5), _row("packed", 10), _row("moderate", 15)]
    sb.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=rows)
    result = await get_status(supabase_client=sb, warung_id="w1")
    assert result["status"] == "packed"
    assert result["is_fresh"] is True
    assert result["report_count"] == 3


@pytest.mark.asyncio
async def test_get_status_falls_back_to_stale_reports_and_flags_them():
    sb = MagicMock()
    # All reports older than the 2-hour fresh window, but within 24h.
    rows = [_row("empty", 180), _row("empty", 200)]
    sb.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=rows)
    result = await get_status(supabase_client=sb, warung_id="w1")
    assert result["status"] == "empty"
    assert result["is_fresh"] is False
    assert result["report_count"] == 2


# ── search_warungs ranking (service layer, not just via the HTTP endpoint) ─

@pytest.mark.asyncio
async def test_search_warungs_ranks_candidates_and_respects_limit():
    sb = MagicMock()
    sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {"id": "w3", "name": "Restoran Pelita", "location": None, "verified": False},
            {"id": "w2", "name": "Pelita Corner Cafe", "location": None, "verified": False},
            {"id": "w1", "name": "Pelita", "location": None, "verified": False},
        ]
    )
    results = await search_warungs(supabase_client=sb, query="Pelita", limit=2)
    assert len(results) == 2
    assert [r["name"] for r in results] == ["Pelita", "Pelita Corner Cafe"]


@pytest.mark.asyncio
async def test_search_warungs_empty_query_returns_empty_without_db_call():
    sb = MagicMock()
    results = await search_warungs(supabase_client=sb, query="   ", limit=10)
    assert results == []
    sb.table.assert_not_called()


# ── core.warung_watch.rank_candidates / select_best_match (pure functions) ─

def test_rank_candidates_orders_exact_prefix_then_rest():
    candidates = [
        {"name": "Kedai Kopi Pelita Baru"},
        {"name": "Restoran Pelita"},
        {"name": "Pelita"},
    ]
    ranked = rank_candidates("Pelita", candidates)
    assert [c["name"] for c in ranked] == ["Pelita", "Restoran Pelita", "Kedai Kopi Pelita Baru"]


def test_rank_candidates_breaks_prefix_ties_by_shortest_name():
    candidates = [
        {"name": "Pelita Corner Cafe And Bakery"},
        {"name": "Pelita Corner"},
    ]
    ranked = rank_candidates("Pelita", candidates)
    assert ranked[0]["name"] == "Pelita Corner"


def test_rank_candidates_case_and_whitespace_insensitive():
    candidates = [{"name": "  PELITA  "}, {"name": "Restoran Pelita"}]
    ranked = rank_candidates("pelita", candidates)
    assert ranked[0]["name"] == "  PELITA  "


def test_select_best_match_returns_top_ranked():
    candidates = [{"name": "Restoran Pelita"}, {"name": "Pelita"}]
    assert select_best_match("Pelita", candidates)["name"] == "Pelita"


def test_select_best_match_empty_candidates_returns_none():
    assert select_best_match("Pelita", []) is None


# ── find_best_warung_match ranking ────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_best_warung_match_prefers_exact_over_prefix():
    sb = MagicMock()
    sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {"id": "w2", "name": "Restoran Pelita", "location": None, "verified": False},
            {"id": "w1", "name": "Pelita", "location": None, "verified": False},
        ]
    )
    match = await find_best_warung_match(supabase_client=sb, query="Pelita")
    assert match is not None
    assert match["name"] == "Pelita"


@pytest.mark.asyncio
async def test_find_best_warung_match_returns_none_for_no_candidates():
    sb = MagicMock()
    sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    match = await find_best_warung_match(supabase_client=sb, query="Nonexistent")
    assert match is None


# ── get_or_create_warung race handling (the confirmed concurrency finding) ─

@pytest.mark.asyncio
async def test_get_or_create_warung_resolves_concurrent_creation_race():
    """Two requests both find no existing row, both attempt to insert — the
    UNIQUE index on normalized_name (032_warung_watch.sql) rejects the
    loser with a 23505. That loser must re-fetch and return the winner's
    row instead of raising or creating a duplicate."""
    sb = MagicMock()
    winner_row = {"id": "warung-1", "name": "Pelita", "normalized_name": "pelita"}

    find_call_count = 0

    def _select_side_effect(*args, **kwargs):
        nonlocal find_call_count
        find_call_count += 1
        # First call (pre-insert check): nothing exists yet. Second call
        # (post-conflict re-fetch): the winner's row is now visible.
        data = [] if find_call_count == 1 else [winner_row]
        result = MagicMock()
        result.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=data)
        return result

    table_mock = MagicMock()
    table_mock.select.side_effect = _select_side_effect

    conflict_error = Exception("duplicate key value violates unique constraint")
    conflict_error.code = "23505"  # type: ignore[attr-defined]
    table_mock.insert.return_value.execute.side_effect = conflict_error

    sb.table.return_value = table_mock

    result = await get_or_create_warung(
        supabase_client=sb, name="Pelita", location=None, lat=None, lng=None, created_by=None,
    )

    assert result == winner_row
    assert find_call_count == 2


@pytest.mark.asyncio
async def test_get_or_create_warung_reraises_non_conflict_errors():
    sb = MagicMock()
    table_mock = MagicMock()
    table_mock.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.insert.return_value.execute.side_effect = RuntimeError("connection reset")
    sb.table.return_value = table_mock

    with pytest.raises(RuntimeError):
        await get_or_create_warung(
            supabase_client=sb, name="Pelita", location=None, lat=None, lng=None, created_by=None,
        )


# ── search_nearby_places (Places API (New) Nearby Search) ─────────────────

@pytest.mark.asyncio
async def test_search_nearby_places_unconfigured_without_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    result = await search_nearby_places(lat=3.1390, lng=101.6869)
    assert result == {"configured": False, "places": []}


@pytest.mark.asyncio
async def test_search_nearby_places_parses_successful_response(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")

    fake_response_body = {
        "places": [
            {
                "id": "place-1",
                "displayName": {"text": "Warung Pelita"},
                "formattedAddress": "Jalan Bukit Bintang, Kuala Lumpur",
                "location": {"latitude": 3.1401, "longitude": 101.6870},
            },
            # Missing displayName — must be skipped, not raise.
            {"id": "place-2", "formattedAddress": "Somewhere"},
        ]
    }

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        assert url == "https://places.googleapis.com/v1/places:searchNearby"
        assert headers["X-Goog-Api-Key"] == "test-key"
        assert "X-Goog-FieldMask" in headers
        assert json["locationRestriction"]["circle"]["center"] == {"latitude": 3.1390, "longitude": 101.6869}
        return httpx.Response(200, json=fake_response_body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await search_nearby_places(lat=3.1390, lng=101.6869)
    assert result["configured"] is True
    assert result["places"] == [
        {
            "place_id": "place-1",
            "name": "Warung Pelita",
            "address": "Jalan Bukit Bintang, Kuala Lumpur",
            "lat": 3.1401,
            "lng": 101.6870,
        }
    ]


@pytest.mark.asyncio
async def test_search_nearby_places_degrades_on_upstream_failure(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        raise httpx.ConnectTimeout("timed out", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await search_nearby_places(lat=3.1390, lng=101.6869)
    assert result == {"configured": True, "places": []}


@pytest.mark.asyncio
async def test_search_nearby_places_degrades_on_http_error_status(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(403, json={"error": "PERMISSION_DENIED"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await search_nearby_places(lat=3.1390, lng=101.6869)
    assert result == {"configured": True, "places": []}


@pytest.mark.asyncio
async def test_search_nearby_places_degrades_on_malformed_response_body(monkeypatch):
    """Confirmed Cursor Bugbot finding: a 200 response whose body doesn't
    match the expected shape (places: null, or a place entry that isn't a
    dict) must degrade like a network failure, not 500 the whole check-in
    flow — Places API (New) is an external contract, not something this
    repo controls the shape of."""
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        return httpx.Response(200, json={"places": None}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await search_nearby_places(lat=3.1390, lng=101.6869)
    assert result == {"configured": True, "places": []}


@pytest.mark.asyncio
async def test_search_nearby_places_degrades_on_non_dict_place_entry(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        return httpx.Response(200, json={"places": ["not-a-dict"]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await search_nearby_places(lat=3.1390, lng=101.6869)
    assert result == {"configured": True, "places": []}


# ── router: GET /nearby ─────────────────────────────────────────────────

def test_nearby_returns_unconfigured_without_key(client, monkeypatch):
    c, *_ = client
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    res = c.get("/api/v1/warung-watch/nearby", params={"lat": 3.1390, "lng": 101.6869})
    assert res.status_code == 200, res.text
    assert res.json() == {"configured": False, "places": []}


def test_nearby_rejects_out_of_range_lat(client):
    c, *_ = client
    res = c.get("/api/v1/warung-watch/nearby", params={"lat": 200.0, "lng": 101.6869})
    assert res.status_code == 422, res.text


def test_nearby_rejects_out_of_range_radius(client):
    c, *_ = client
    res = c.get("/api/v1/warung-watch/nearby", params={"lat": 3.1390, "lng": 101.6869, "radius_m": 99999})
    assert res.status_code == 422, res.text


def test_nearby_rate_limit_boundary(client, monkeypatch):
    """20/minute per the router's @anonymous_limiter.limit("20/minute") —
    the 21st call in one minute from the same client must 429."""
    c, *_ = client
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    params = {"lat": 3.1390, "lng": 101.6869}
    for _ in range(20):
        res = c.get("/api/v1/warung-watch/nearby", params=params)
        assert res.status_code == 200, res.text
    res = c.get("/api/v1/warung-watch/nearby", params=params)
    assert res.status_code == 429, res.text
