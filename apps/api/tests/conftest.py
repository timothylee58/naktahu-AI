"""Shared test fixtures — centralized to prevent duplication.

Adopts Merlion OS pattern: conftest.py holds ALL auth headers, mock clients,
and shared state reset. Every test file imports from here, eliminating
copy-paste and ensuring consistency.

Key principles:
1. Autouse fixtures reset all module-level state before every test
2. Auth headers are generated once, reused everywhere
3. Standardized mock factories prevent inconsistency
4. All external I/O is mocked (Redis, Supabase, LLM)
"""
from unittest.mock import AsyncMock, MagicMock
import time
import jwt

import pytest

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


# ─────────────────────────────────────────────────────────────────────────────
# AUTOUSE FIXTURES: Reset all shared state before every test
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_shared_state(monkeypatch):
    """Merlion OS Pattern: Clean slate for every test.

    Resets:
    - Rate-limit ledgers (anonymous + authenticated)
    - Redis mock state
    - Supabase mock state
    - Agent checkpointer
    - Webhook event ledger (if applicable)

    This prevents test order dependencies and state leakage.
    """
    # Reset rate limiters
    anonymous_limiter.reset()
    authenticated_limiter.reset()

    # Reset Redis state
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.lrange = AsyncMock(return_value=[])
    redis_client.aclose = AsyncMock(return_value=None)
    redis_client.incr = AsyncMock(return_value=1)
    redis_client.expire = AsyncMock(return_value=True)
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=1)

    pipe = MagicMock()
    pipe.lpush.return_value = pipe
    pipe.ltrim.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    def fake_from_url(*args, **kwargs):
        return redis_client

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    # Reset Supabase state
    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[{}])
    table_mock = MagicMock()
    table_mock.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.insert.return_value = insert_mock
    table_mock.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    table_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    sb = MagicMock()
    sb.table.return_value = table_mock

    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    # Reset agent checkpointer
    try:
        from app.agents.checkpointer import reset_checkpointer_for_tests
        reset_checkpointer_for_tests()
    except ImportError:
        pass  # Checkpointer may not exist in all contexts

    yield {"redis": redis_client, "supabase": sb, "insert_chain": insert_mock}

    # Cleanup
    anonymous_limiter.reset()
    authenticated_limiter.reset()


# ─────────────────────────────────────────────────────────────────────────────
# AUTH & API KEY FIXTURES: Declarative header generation
# ─────────────────────────────────────────────────────────────────────────────

def _make_auth_headers(user_id: str = "test-user-1", plan: str = "pro") -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": user_id,
            "aud": settings.supabase_jwt_aud,
            "app_metadata": {"plan": plan},
            "exp": int(time.time()) + 3600,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Generate valid JWT for authenticated testing (default: pro plan).

    Returns a plain dict, not a factory — use auth_headers_free/_student/_business
    for other plans rather than trying to call this fixture with arguments
    (pytest injects the fixture's return value, not the function itself).

    Example:
        def test_history_requires_auth(client, auth_headers):
            resp = client.get("/api/v1/history", headers=auth_headers)
            assert resp.status_code == 200
    """
    return _make_auth_headers(user_id="test-user-1", plan="pro")


@pytest.fixture
def auth_headers_free() -> dict[str, str]:
    """Shorthand: Free plan user."""
    return _make_auth_headers(user_id="test-free-user", plan="free")


@pytest.fixture
def auth_headers_student() -> dict[str, str]:
    """Shorthand: Student plan user."""
    return _make_auth_headers(user_id="test-student-user", plan="student")


@pytest.fixture
def auth_headers_business() -> dict[str, str]:
    """Shorthand: Business plan user."""
    return _make_auth_headers(user_id="test-biz-user", plan="business")


@pytest.fixture
def auth_headers_anonymous() -> dict[str, str]:
    """Generate headers for anonymous (unauthenticated) requests."""
    return {}


@pytest.fixture
def api_key_headers(api_key: str = "nkt_live_test_abc123xyz789") -> dict[str, str]:
    """Generate API key headers for Developer/Public API testing.

    Args:
        api_key: Raw API key (default: test key, nkt_live_ prefix per
            services/api_key_service.py's API_KEY_RAW_PREFIX)

    Returns:
        dict with "X-NakTahu-Key: {key}" header — the real header name
        middleware/api_key_auth.py checks, not X-API-Key.

    Example:
        def test_public_query_requires_key(client, api_key_headers):
            resp = client.post("/api/v1/public/query", json={"query": "..."}, headers=api_key_headers)
    """
    return {"X-NakTahu-Key": api_key}


# ─────────────────────────────────────────────────────────────────────────────
# MOCK FIXTURES: Standardized mocks
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_supabase():
    """Standardized Supabase mock with full CRUD chain."""
    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[{"id": "mock-1"}])

    select_mock = MagicMock()
    select_mock.limit.return_value.execute.return_value = MagicMock(data=[])

    update_mock = MagicMock()
    update_mock.eq.return_value.execute.return_value = MagicMock(data=[])

    delete_mock = MagicMock()
    delete_mock.eq.return_value.execute.return_value = MagicMock(data=[])

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    table_mock.insert.return_value = insert_mock
    table_mock.update.return_value = update_mock
    table_mock.delete.return_value = delete_mock

    sb = MagicMock()
    sb.table.return_value = table_mock

    return sb


@pytest.fixture
def mock_redis():
    """Standardized Redis mock."""
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.incr = AsyncMock(return_value=1)
    redis_client.expire = AsyncMock(return_value=True)
    redis_client.lrange = AsyncMock(return_value=[])
    redis_client.lpush = AsyncMock(return_value=1)
    redis_client.ltrim = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)

    pipe = MagicMock()
    pipe.lpush.return_value = pipe
    pipe.ltrim.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    return redis_client


@pytest.fixture
def mock_llm_client():
    """Standardized LLM client mock (ILMU + Claude fallback)."""
    mock = AsyncMock()
    mock.invoke = AsyncMock(return_value="Test response")
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT FIXTURES: FastAPI TestClient with pre-configured app
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """FastAPI TestClient for root main.py."""
    from fastapi.testclient import TestClient
    return TestClient(api_main.app)


@pytest.fixture
def app_client():
    """FastAPI TestClient for app/main.py (deployed version)."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
