import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter
from services import auth as auth_mod


def _token(sub: str = "user-1", exp_seconds: int = 3600) -> str:
    return jwt.encode(
        {
            "sub": sub,
            "aud": settings.supabase_jwt_aud,
            "exp": int(time.time()) + exp_seconds,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    redis_client.lrange = AsyncMock(return_value=[])

    pipe = MagicMock()
    pipe.lpush.return_value = pipe
    pipe.ltrim.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    def fake_from_url(*args, **kwargs):
        return redis_client

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    sb = MagicMock()
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c


def test_history_missing_token_returns_401(client):
    res = client.get("/api/v1/history")
    assert res.status_code == 401


def test_jwt_decode_mock_valid(monkeypatch):
    monkeypatch.setattr(
        auth_mod.jwt,
        "get_unverified_header",
        lambda token: {"alg": "HS256"},
    )
    monkeypatch.setattr(
        auth_mod.jwt,
        "decode",
        lambda token, key, algorithms=None, audience=None, options=None: {"sub": "mock-user"},
    )

    async def run():
        return await auth_mod.get_current_user(token="tok")

    ctx = asyncio.run(run())
    assert ctx.user_id == "mock-user"
    assert ctx.is_anonymous is False


def test_jwt_decode_es256_via_jwks(monkeypatch):
    """Current Supabase projects sign with an asymmetric key (ES256) served
    from the project's JWKS endpoint rather than a shared HS256 secret —
    _decode_supabase_jwt must branch on the token's own `alg` header and
    verify against the matching key material, not always assume HS256."""
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(
        {
            "sub": "es256-user",
            "aud": settings.supabase_jwt_aud,
            "exp": int(time.time()) + 3600,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "test-kid"},
    )

    fake_signing_key = MagicMock()
    fake_signing_key.key = private_key.public_key()
    monkeypatch.setattr(
        auth_mod._jwks_client,
        "get_signing_key_from_jwt",
        lambda tok: fake_signing_key,
    )

    async def run():
        return await auth_mod.get_current_user(token=token)

    ctx = asyncio.run(run())
    assert ctx.user_id == "es256-user"
    assert ctx.is_anonymous is False


def test_jwt_decode_mock_expired(monkeypatch):
    import jwt as pyjwt

    def boom(*args, **kwargs):
        raise pyjwt.ExpiredSignatureError("expired")

    monkeypatch.setattr(auth_mod.jwt, "decode", boom)

    async def run():
        return await auth_mod.get_optional_user(token="tok")

    assert asyncio.run(run()) is None


def test_jwt_decode_mock_missing_optional():
    async def run():
        return await auth_mod.get_optional_user(token=None)

    assert asyncio.run(run()) is None


def test_anonymous_query_rate_limit_31st_returns_429_with_retry_after(client):
    for i in range(30):
        r = client.post("/api/v1/query", json={"query": f"q{i}"})
        assert r.status_code == 200, r.text
    r31 = client.post("/api/v1/query", json={"query": "blocked"})
    assert r31.status_code == 429
    lowered = {k.lower(): v for k, v in r31.headers.items()}
    assert "retry-after" in lowered


def test_authenticated_query_uses_user_bucket(monkeypatch, client):
    for i in range(30):
        client.post("/api/v1/query", json={"query": f"anon-{i}"})
    blocked = client.post("/api/v1/query", json={"query": "still-anon"})
    assert blocked.status_code == 429

    tok = _token(sub="user-separated")
    headers = {"Authorization": f"Bearer {tok}"}
    ok = client.post("/api/v1/query", json={"query": "authed"}, headers=headers)
    assert ok.status_code == 200, ok.text
