"""_stream_pipeline observes time-to-first-token exactly once per request."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.prometheus_metrics import time_to_first_token_seconds
from app.routers import query as query_router


def _count() -> float:
    return next(s.value for s in time_to_first_token_seconds.collect()[0].samples if s.name.endswith("_count"))


@pytest.mark.asyncio
async def test_first_token_latency_observed_once_not_per_token() -> None:
    async def fake_run(*args, on_token=None, **kwargs):
        for t in ("a", "b", "c"):
            await on_token(t)
        return {"tokens": ["a", "b", "c"], "final_state": {}, "metrics": {}}

    before = _count()
    with patch.object(query_router, "_run_pipeline", fake_run):
        events = [e async for e in query_router._stream_pipeline("q", "s", None)]

    assert [k for k, _ in events] == ["token", "token", "token", "result"]
    assert _count() == before + 1


@pytest.mark.asyncio
async def test_no_tokens_means_no_first_token_observation() -> None:
    async def fake_run(*args, on_token=None, **kwargs):
        return {"tokens": [], "final_state": {}, "metrics": {}}

    before = _count()
    with patch.object(query_router, "_run_pipeline", fake_run):
        [e async for e in query_router._stream_pipeline("q", "s", None)]

    assert _count() == before
