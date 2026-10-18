import time
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter
from services.daily_quota import FREE_DAILY_LIMIT


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def get(self, key: str):
        return self.store.get(key)


def _auth(sub: str = "quota-user", plan: str | None = None) -> dict[str, str]:
    claims = {"sub": sub, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600}
    if plan:
        claims["app_metadata"] = {"plan": plan}
    tok = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(monkeypatch):
    redis_client = FakeRedis()
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)
    monkeypatch.setattr(api_main, "create_client", lambda url, key: MagicMock())
    anonymous_limiter.reset()
    authenticated_limiter.reset()
    with TestClient(api_main.app) as c:
        yield c, redis_client


def test_anonymous_sees_limit_and_zero_used(client):
    c, _ = client
    body = c.get("/api/v1/quota/daily").json()
    assert body == {"used": 0, "limit": FREE_DAILY_LIMIT, "unlimited": False, "authenticated": False}


def test_anonymous_used_count_reflects_redis(client):
    c, redis = client

    async def fake_get(key: str):
        return "7" if key.startswith("quota:daily:anon:") else None

    redis.get = fake_get
    assert c.get("/api/v1/quota/daily").json()["used"] == 7


def test_used_is_capped_at_limit(client):
    c, redis = client

    async def fake_get(key: str):
        return "999"

    redis.get = fake_get
    assert c.get("/api/v1/quota/daily").json()["used"] == FREE_DAILY_LIMIT


def test_authenticated_free_user_is_keyed_by_user_id(client):
    c, redis = client
    seen: list[str] = []

    async def fake_get(key: str):
        seen.append(key)
        return "3"

    redis.get = fake_get
    body = c.get("/api/v1/quota/daily", headers=_auth()).json()
    assert body["used"] == 3 and body["authenticated"] is True
    assert any(":auth:quota-user:" in k for k in seen)


def test_paid_plan_is_unlimited(client):
    c, _ = client
    body = c.get("/api/v1/quota/daily", headers=_auth(plan="pro")).json()
    assert body["unlimited"] is True and body["limit"] is None


def test_redis_failure_degrades_to_zero(client):
    c, redis = client

    async def boom(key: str):
        raise RuntimeError("redis down")

    redis.get = boom
    res = c.get("/api/v1/quota/daily")
    assert res.status_code == 200 and res.json()["used"] == 0


def test_rate_limit_boundary(client):
    c, _ = client
    codes = [c.get("/api/v1/quota/daily").status_code for _ in range(61)]
    assert codes[:60] == [200] * 60 and codes[60] == 429
