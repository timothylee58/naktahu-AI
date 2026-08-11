import asyncio
import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter
from services.history import fetch_history_entries


def _auth_header(sub: str = "hist-user", plan: str = "pro") -> dict[str, str]:
    tok = jwt.encode(
        {
            "sub": sub,
            "aud": settings.supabase_jwt_aud,
            "exp": int(time.time()) + 3600,
            "app_metadata": {"plan": plan},
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    redis_client.lrange = AsyncMock(return_value=[])

    pipe = MagicMock()
    pipe.lpush.return_value = pipe
    pipe.rpush.return_value = pipe
    pipe.ltrim.return_value = pipe
    pipe.expire.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    def fake_from_url(*args, **kwargs):
        return redis_client

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[{"id": "1"}])
    table_mock = MagicMock()
    table_mock.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    # user_sessions fallback-read chain: .select(...).eq(...).order(...).limit(...).execute()
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.insert.return_value = insert_mock

    sb = MagicMock()
    sb.table.return_value = table_mock

    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, redis_client, sb, insert_mock


def test_get_history_401_without_auth(client):
    c, *_ = client
    res = c.get("/api/v1/history")
    assert res.status_code == 401


def test_get_history_403_on_free_plan(client):
    c, *_ = client
    res = c.get("/api/v1/history", headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 403


def test_get_history_200_for_primary_admin(client):
    c, redis_client, *_ = client
    redis_client.lrange = AsyncMock(return_value=[])
    tok = jwt.encode(
        {
            "sub": "admin-user",
            "aud": settings.supabase_jwt_aud,
            "exp": int(time.time()) + 3600,
            "app_metadata": {"plan": "business", "role": "primary_admin"},
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    res = c.get("/api/v1/history", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 200
    assert res.json() == []


def test_post_history_403_on_free_plan(client):
    c, *_ = client
    body = {
        "query": "What is VAT?",
        "language": "ms",
        "domain": "tax",
        "response_summary": "VAT is a consumption tax.",
        "citations": [],
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 403


def test_post_history_rejects_unknown_domain(client):
    c, *_ = client
    body = {
        "query": "What is VAT?",
        "language": "en",
        "domain": "not-a-real-domain",
        "response_summary": "VAT is a consumption tax.",
        "citations": [],
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header())
    assert res.status_code == 422


def test_post_history_rejects_unknown_language(client):
    c, *_ = client
    body = {
        "query": "What is VAT?",
        "language": "klingon",
        "domain": "tax",
        "response_summary": "VAT is a consumption tax.",
        "citations": [],
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header())
    assert res.status_code == 422


def test_post_history_normalises_ms_alias_to_bm(client):
    """router_node/guard_node only special-case "bm", not "ms" — the "ms"
    input alias must be normalised before it reaches persisted storage or
    any downstream pipeline code that only checks for "bm"."""
    c, redis_client, sb, _ = client
    body = {
        "query": "What is VAT?",
        "language": "ms",
        "domain": "tax",
        "response_summary": "VAT is a consumption tax.",
        "citations": [],
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header())
    assert res.status_code == 201
    pipe = redis_client.pipeline.return_value
    stored = json.loads(pipe.lpush.call_args[0][1])
    assert stored["language"] == "bm"


def test_post_history_rejects_empty_query(client):
    c, *_ = client
    body = {
        "query": "",
        "language": "en",
        "domain": "tax",
        "response_summary": "VAT is a consumption tax.",
        "citations": [],
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header())
    assert res.status_code == 422


def test_post_history_rejects_oversized_citations_list(client):
    c, *_ = client
    body = {
        "query": "What is VAT?",
        "language": "en",
        "domain": "tax",
        "response_summary": "VAT is a consumption tax.",
        "citations": [{"url": "https://x.com"}] * 101,
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header())
    assert res.status_code == 422


def test_post_history_persists_redis_and_supabase(client):
    c, redis_client, sb, insert_mock = client
    stored = json.dumps(
        {
            "query": "What is VAT?",
            "language": "ms",
            "domain": "tax",
            "response_summary": "VAT is a consumption tax applied at each stage.",
            "citations": [{"url": "https://example.com"}],
        }
    )
    redis_client.lrange = AsyncMock(return_value=[stored])

    body = {
        "query": "What is VAT?",
        "language": "ms",
        "domain": "tax",
        "response_summary": "VAT is a consumption tax applied at each stage.",
        "citations": [{"url": "https://example.com"}],
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header())
    assert res.status_code == 201
    redis_client.pipeline.assert_called()
    pipe = redis_client.pipeline.return_value
    pipe.lpush.assert_called_once()
    pipe.ltrim.assert_called_once()
    pipe.expire.assert_called_once()
    pipe.execute.assert_called_once()
    sb.table.assert_called_with("user_sessions")
    insert_mock.execute.assert_called_once()


def test_get_history_falls_back_to_supabase_when_redis_empty(client):
    """Redis restarts/evicts without warning — a registered user's history
    must not appear to vanish just because the Redis cache is cold."""
    c, redis_client, sb, _ = client
    redis_client.lrange = AsyncMock(return_value=[])

    supabase_rows = [
        {
            "query": "What is VAT?",
            "language": "ms",
            "domain": "tax",
            "response_summary": "VAT is a consumption tax.",
            "citations": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=supabase_rows
    )

    res = c.get("/api/v1/history", headers=_auth_header())
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["query"] == "What is VAT?"
    assert body[0]["ts"] == int(datetime.fromisoformat("2026-01-01T00:00:00+00:00").timestamp())

    # Cache warming: the Supabase-sourced entries should be written back to
    # Redis so the next request for this user hits the fast path.
    pipe = redis_client.pipeline.return_value
    pipe.rpush.assert_called_once()
    warmed_key, *warmed_items = pipe.rpush.call_args[0]
    assert warmed_key == "session_history:hist-user"
    assert len(warmed_items) == 1
    assert json.loads(warmed_items[0])["query"] == "What is VAT?"
    pipe.expire.assert_called_once()
    assert pipe.expire.call_args[0][1] == 30 * 24 * 60 * 60


def test_get_history_survives_redis_connection_error(client):
    """A live Redis outage (not just an empty/cold key) must fall back to
    Supabase and return 200 — not surface as a 500 to the user."""
    c, redis_client, sb, _ = client
    redis_client.lrange = AsyncMock(side_effect=ConnectionError("connection refused"))

    supabase_rows = [
        {
            "query": "Redis is down but this still works",
            "language": "en",
            "domain": "government",
            "response_summary": "Fallback path",
            "citations": [],
            "created_at": "2026-01-02T00:00:00+00:00",
        }
    ]
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=supabase_rows
    )

    res = c.get("/api/v1/history", headers=_auth_header())
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["query"] == "Redis is down but this still works"


def test_get_history_cache_warm_failure_does_not_break_the_response(client):
    """If Redis is unreachable for the warm-back write too, the user still
    gets their (correct) Supabase-sourced history — warming is best-effort."""
    c, redis_client, sb, _ = client
    redis_client.lrange = AsyncMock(return_value=[])
    pipe = redis_client.pipeline.return_value
    pipe.execute = AsyncMock(side_effect=ConnectionError("connection refused"))

    supabase_rows = [
        {
            "query": "Warm write fails but read still succeeds",
            "language": "en",
            "domain": "government",
            "response_summary": "ok",
            "citations": [],
            "created_at": "2026-01-03T00:00:00+00:00",
        }
    ]
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=supabase_rows
    )

    res = c.get("/api/v1/history", headers=_auth_header())
    assert res.status_code == 200
    assert res.json()[0]["query"] == "Warm write fails but read still succeeds"


def test_get_history_survives_supabase_exception(client):
    """Both stores unavailable at once must degrade to an empty list, not a
    500 — matches the existing history_redis_unavailable degrade pattern."""
    c, redis_client, sb, _ = client
    redis_client.lrange = AsyncMock(return_value=[])
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = (
        Exception("Supabase unreachable")
    )

    res = c.get("/api/v1/history", headers=_auth_header())
    assert res.status_code == 200
    assert res.json() == []


def test_get_history_skips_row_with_malformed_created_at(client):
    """A malformed timestamp must not crash the whole response — just that
    entry's ts falls back to None rather than poisoning the request."""
    c, redis_client, sb, _ = client
    redis_client.lrange = AsyncMock(return_value=[])
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "query": "Bad timestamp",
                "language": "en",
                "domain": "government",
                "response_summary": "ok",
                "citations": [],
                "created_at": "not-a-real-timestamp",
            }
        ]
    )

    res = c.get("/api/v1/history", headers=_auth_header())
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["ts"] is None


def test_get_history_preserves_newest_first_order_from_supabase(client):
    """Supabase already orders newest-first; the response (and the warmed
    Redis list) must preserve that order, not reverse or reshuffle it."""
    c, redis_client, sb, _ = client
    redis_client.lrange = AsyncMock(return_value=[])
    rows = [
        {
            "query": f"query-{i}",
            "language": "en",
            "domain": "government",
            "response_summary": "ok",
            "citations": [],
            "created_at": f"2026-01-{10 - i:02d}T00:00:00+00:00",
        }
        for i in range(3)
    ]
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=rows
    )

    res = c.get("/api/v1/history", headers=_auth_header())
    body = res.json()
    assert [e["query"] for e in body] == ["query-0", "query-1", "query-2"]

    pipe = redis_client.pipeline.return_value
    _, *warmed_items = pipe.rpush.call_args[0]
    warmed_queries = [json.loads(item)["query"] for item in warmed_items]
    assert warmed_queries == ["query-0", "query-1", "query-2"]


def test_get_history_prefers_redis_when_present(client):
    """Redis is checked first — Supabase is only consulted as a fallback."""
    c, redis_client, sb, _ = client
    redis_client.lrange = AsyncMock(
        return_value=[
            json.dumps(
                {
                    "query": "Redis-sourced query",
                    "language": "en",
                    "domain": "tax",
                    "response_summary": "From cache",
                    "citations": [],
                    "ts": 1700000000,
                }
            )
        ]
    )

    res = c.get("/api/v1/history", headers=_auth_header())
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["query"] == "Redis-sourced query"
    sb.table.return_value.select.return_value.eq.assert_not_called()


def test_get_history_returns_empty_when_both_redis_and_supabase_empty(client):
    c, redis_client, sb, _ = client
    redis_client.lrange = AsyncMock(return_value=[])

    res = c.get("/api/v1/history", headers=_auth_header())
    assert res.status_code == 200
    assert res.json() == []


def test_history_authenticated_rate_limit_201st_returns_429(client):
    c, *_ = client
    headers = _auth_header(sub="hist-rate-user")
    for i in range(200):
        r = c.get("/api/v1/history", headers=headers)
        assert r.status_code == 200, r.text
    blocked = c.get("/api/v1/history", headers=headers)
    assert blocked.status_code == 429
    lowered = {k.lower(): v for k, v in blocked.headers.items()}
    assert "retry-after" in lowered


# ---------------------------------------------------------------------------
# Stress / concurrency: cold-cache thundering herd on fetch_history_entries.
# Calls the service function directly — HTTP-layer concurrency isn't
# meaningfully exercised by TestClient's synchronous request cycle, but the
# race this fix cares about (many concurrent readers all hitting Supabase
# while Redis is cold, then all trying to warm the cache) lives entirely in
# the service function.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_history_entries_concurrent_cold_cache_reads_stable():
    """50 concurrent readers hitting a cold cache simultaneously must each
    get the correct data, and the concurrent cache-warming writes must not
    raise even though they race each other."""
    redis_client = AsyncMock()
    redis_client.lrange = AsyncMock(return_value=[])

    pipe = MagicMock()
    pipe.rpush.return_value = pipe
    pipe.expire.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    supabase_rows = [
        {
            "query": "Concurrent read query",
            "language": "en",
            "domain": "government",
            "response_summary": "ok",
            "citations": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    table_mock = MagicMock()
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=supabase_rows
    )
    sb = MagicMock()
    sb.table.return_value = table_mock

    results = await asyncio.gather(
        *[fetch_history_entries(redis_client, sb, "stress-user") for _ in range(50)]
    )

    assert len(results) == 50
    for r in results:
        assert len(r) == 1
        assert r[0]["query"] == "Concurrent read query"
    # Every concurrent caller independently warmed the cache — wasteful but
    # harmless (idempotent overwrite), and critically: none of them raised.
    assert pipe.rpush.call_count == 50


@pytest.mark.asyncio
async def test_fetch_history_entries_concurrent_reads_survive_flaky_redis():
    """Under concurrent load, some readers hit a Redis that's mid-outage and
    some don't (real-world restart/failover) — every caller must still get
    correct data via the Supabase fallback, none may raise."""
    redis_client = AsyncMock()
    call_count = {"n": 0}

    async def _flaky_lrange(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] % 2 == 0:
            raise ConnectionError("intermittent connection refused")
        return []

    redis_client.lrange = _flaky_lrange

    pipe = MagicMock()
    pipe.rpush.return_value = pipe
    pipe.expire.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    supabase_rows = [
        {
            "query": "Flaky redis query",
            "language": "en",
            "domain": "government",
            "response_summary": "ok",
            "citations": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    table_mock = MagicMock()
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=supabase_rows
    )
    sb = MagicMock()
    sb.table.return_value = table_mock

    results = await asyncio.gather(
        *[fetch_history_entries(redis_client, sb, "flaky-user") for _ in range(20)],
        return_exceptions=True,
    )

    assert len(results) == 20
    for r in results:
        assert not isinstance(r, Exception), f"fetch_history_entries raised: {r}"
        assert r[0]["query"] == "Flaky redis query"


@pytest.mark.asyncio
async def test_fetch_history_entries_large_supabase_result_is_capped():
    """Even if Supabase somehow returns more than MAX_HISTORY rows (e.g. a
    future query change), the caller must not choke on an oversized list —
    the limit is enforced at the query level, but defend the shape here too."""
    redis_client = AsyncMock()
    redis_client.lrange = AsyncMock(return_value=[])
    redis_client.pipeline = MagicMock(return_value=MagicMock(
        rpush=MagicMock(return_value=MagicMock(
            expire=MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=[])))
        )),
    ))

    rows = [
        {
            "query": f"query-{i}",
            "language": "en",
            "domain": "government",
            "response_summary": "ok",
            "citations": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        for i in range(100)
    ]
    table_mock = MagicMock()
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=rows
    )
    sb = MagicMock()
    sb.table.return_value = table_mock

    result = await fetch_history_entries(redis_client, sb, "large-user")
    assert len(result) == 100  # documents current behaviour: no client-side cap
    table_mock.select.return_value.eq.return_value.order.return_value.limit.assert_called_with(20)


def _configure_delete(sb, returned_rows):
    sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=returned_rows
    )


def _configure_update(sb, returned_rows):
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=returned_rows
    )


def test_delete_history_entry_401_without_auth(client):
    c, *_ = client
    res = c.delete("/api/v1/history/some-id")
    assert res.status_code == 401


def test_delete_history_entry_403_on_free_plan(client):
    c, *_ = client
    res = c.delete("/api/v1/history/some-id", headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 403


def test_delete_history_entry_204_on_success(client):
    c, redis_client, sb, _ = client
    _configure_delete(sb, [{"id": "abc-123"}])
    res = c.delete("/api/v1/history/abc-123", headers=_auth_header())
    assert res.status_code == 204
    redis_client.delete.assert_awaited()


def test_delete_history_entry_404_when_not_found_or_not_owned(client):
    c, _, sb, _ = client
    _configure_delete(sb, [])
    res = c.delete("/api/v1/history/does-not-exist", headers=_auth_header())
    assert res.status_code == 404


def test_delete_history_entry_503_when_supabase_degraded(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.delete("/api/v1/history/abc-123", headers=_auth_header())
    assert res.status_code == 503


def test_rename_history_entry_401_without_auth(client):
    c, *_ = client
    res = c.patch("/api/v1/history/some-id", json={"title": "New title"})
    assert res.status_code == 401


def test_rename_history_entry_403_on_free_plan(client):
    c, *_ = client
    res = c.patch(
        "/api/v1/history/some-id",
        json={"title": "New title"},
        headers=_auth_header(sub="free-user", plan="free"),
    )
    assert res.status_code == 403


def test_rename_history_entry_422_on_empty_title(client):
    c, *_ = client
    res = c.patch("/api/v1/history/abc-123", json={"title": ""}, headers=_auth_header())
    assert res.status_code == 422


def test_rename_history_entry_200_on_success(client):
    c, redis_client, sb, _ = client
    _configure_update(sb, [{"id": "abc-123", "title": "New title"}])
    res = c.patch("/api/v1/history/abc-123", json={"title": "New title"}, headers=_auth_header())
    assert res.status_code == 200
    assert res.json() == {"status": "renamed"}
    redis_client.delete.assert_awaited()


def test_rename_history_entry_404_when_not_found_or_not_owned(client):
    c, _, sb, _ = client
    _configure_update(sb, [])
    res = c.patch("/api/v1/history/does-not-exist", json={"title": "New title"}, headers=_auth_header())
    assert res.status_code == 404


def test_rename_history_entry_503_when_supabase_degraded(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.patch("/api/v1/history/abc-123", json={"title": "New title"}, headers=_auth_header())
    assert res.status_code == 503


# ── GET /api/v1/agent-runs ─────────────────────────────────────────────
# Plain-auth (not require_plan("pro")) since the underlying agents span
# every plan tier — a free-tier health-triage/retrenchment-navigator user
# must still see their own past output.

_AGENT_RUN_ROW = {
    "id": "run-1",
    "agent_name": "retrenchment-navigator",
    "session_id": "sess-1",
    "output": {"checklist": ["File EIS claim"], "status": "completed"},
    "completion_status": "completed",
    "turns_count": 3,
    "created_at": "2024-01-01T00:00:00Z",
}


def test_get_agent_runs_401_without_auth(client):
    c, *_ = client
    res = c.get("/api/v1/agent-runs")
    assert res.status_code == 401


def test_get_agent_runs_200_for_free_plan_user(client):
    """Confirms this endpoint is NOT plan-gated like /history — a free-tier
    user must be able to list their own agent runs."""
    c, _, sb, _ = client
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_AGENT_RUN_ROW]
    )
    res = c.get("/api/v1/agent-runs", headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 200, res.text
    assert res.json() == [_AGENT_RUN_ROW]


def test_get_agent_runs_filters_by_agent_name(client):
    c, _, sb, _ = client
    table_mock = sb.table.return_value
    # Two `.eq()` calls in the chain when agent_name is passed (user_id,
    # then agent_name) — distinct from the single-.eq() chain the other
    # /history tests configure.
    table_mock.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_AGENT_RUN_ROW]
    )
    res = c.get(
        "/api/v1/agent-runs",
        params={"agent_name": "retrenchment-navigator"},
        headers=_auth_header(sub="free-user", plan="free"),
    )
    assert res.status_code == 200, res.text
    assert res.json() == [_AGENT_RUN_ROW]


def test_get_agent_runs_rejects_out_of_range_limit(client):
    c, *_ = client
    res = c.get("/api/v1/agent-runs", params={"limit": 999}, headers=_auth_header())
    assert res.status_code == 422


def test_get_agent_runs_503_when_supabase_degraded(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.get("/api/v1/agent-runs", headers=_auth_header())
    assert res.status_code == 503


def test_get_agent_runs_degrades_to_empty_list_on_fetch_error(client):
    c, _, sb, _ = client
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = RuntimeError(
        "connection reset"
    )
    res = c.get("/api/v1/agent-runs", headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 200, res.text
    assert res.json() == []


# ── GET /api/v1/agent-runs/{run_id} ────────────────────────────────────
# Backs the "resume a past session" flow every agent page uses — sourced
# from agent_runs (not per-agent checkpoint state) since two agents
# (research-synthesiser, sme-compliance-navigator) compile with no
# checkpointer at all and have nothing else to resume from.

def test_get_agent_run_by_id_401_without_auth(client):
    c, *_ = client
    res = c.get("/api/v1/agent-runs/run-1")
    assert res.status_code == 401


def test_get_agent_run_by_id_200_for_owner(client):
    c, _, sb, _ = client
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[_AGENT_RUN_ROW]
    )
    res = c.get("/api/v1/agent-runs/run-1", headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 200, res.text
    assert res.json() == _AGENT_RUN_ROW


def test_get_agent_run_by_id_404_when_not_found_or_not_owned(client):
    """Confirms the same 404 for a genuinely missing run and one that
    belongs to someone else — a distinct response would confirm the
    run_id is valid for another user."""
    c, _, sb, _ = client
    table_mock = sb.table.return_value
    table_mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    res = c.get("/api/v1/agent-runs/not-mine", headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 404


def test_get_agent_run_by_id_503_when_supabase_degraded(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.get("/api/v1/agent-runs/run-1", headers=_auth_header())
    assert res.status_code == 503
