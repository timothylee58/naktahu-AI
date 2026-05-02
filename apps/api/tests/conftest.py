from unittest.mock import AsyncMock, MagicMock

import pytest

import main as api_main
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    anonymous_limiter.reset()
    authenticated_limiter.reset()
    yield
    anonymous_limiter.reset()
    authenticated_limiter.reset()


@pytest.fixture(autouse=True)
def patch_redis_and_supabase_startup(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.lrange = AsyncMock(return_value=[])
    redis_client.aclose = AsyncMock(return_value=None)

    pipe = MagicMock()
    pipe.lpush.return_value = pipe
    pipe.ltrim.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    def fake_from_url(*args, **kwargs):
        return redis_client

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[{}])
    table_mock = MagicMock()
    table_mock.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.insert.return_value = insert_mock

    sb = MagicMock()
    sb.table.return_value = table_mock

    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    yield {"redis": redis_client, "supabase": sb, "insert_chain": insert_mock}
