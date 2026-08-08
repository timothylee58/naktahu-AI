"""Warung Watch: router auth/validation/degraded-mode boundaries, plus
direct unit coverage of get_status()'s aggregation math — the "trust
layer" for this feature (equivalent to analyst_node's confidence check
elsewhere in this repo), since that's what stops a single stale or
mismatched report from being presented as current fact.
"""
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter
from services.warung_watch import get_status, normalize_name


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


def test_status_no_matching_warung(client):
    c, sb, warungs_table, checkins_table = client
    warungs_table.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    res = c.get("/api/v1/warung-watch/status", params={"name": "Nonexistent"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] is None


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
