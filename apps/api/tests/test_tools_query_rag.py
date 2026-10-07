"""Tests for app.agents.tools.query_rag / query_rag_findings.

Every vertical-agent test mocks query_rag_findings wholesale, so none of them
ever exercised the real call into vector_store.hybrid_search — which is how a
wrong-keyword call (query_embedding=/query_text=/language=/top_k=) shipped and
raised TypeError on every invocation. These tests call the real function with
hybrid_search autospec'd, so any signature mismatch fails here.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents import tools
from app.services.vector_store import ChunkResult, hybrid_search

_EMBEDDING = [0.1] * 1536
_CHUNK = ChunkResult(
    id="c1",
    content="Kadar caruman KWSP majikan ialah 13%.",
    source_title="KWSP",
    source_url="https://www.kwsp.gov.my",
    ministry="KWSP",
    language="bm",
    similarity=0.8,
)


@pytest.mark.asyncio
async def test_query_rag_calls_hybrid_search_with_its_real_signature() -> None:
    with (
        patch("app.agents.tools._embed", AsyncMock(return_value=_EMBEDDING)),
        patch("app.agents.tools.hybrid_search", autospec=True, return_value=[_CHUNK]) as search,
    ):
        result = await tools.query_rag("caruman KWSP", "epf", top_k=3)

    search.assert_awaited_once_with("caruman KWSP", _EMBEDDING, domain="epf", limit=3)
    assert result[0]["id"] == "c1"
    assert result[0]["source_url"] == "https://www.kwsp.gov.my"


@pytest.mark.asyncio
async def test_query_rag_findings_returns_findings_not_a_typeerror() -> None:
    with (
        patch("app.agents.tools._embed", AsyncMock(return_value=_EMBEDDING)),
        patch("app.agents.tools.hybrid_search", autospec=True, return_value=[_CHUNK]),
    ):
        findings = await tools.query_rag_findings("caruman KWSP", "epf")

    assert findings == [
        {
            "domain": "epf",
            "summary": _CHUNK.content,
            "source_title": "KWSP",
            "source_url": "https://www.kwsp.gov.my",
            "similarity": 0.8,
        }
    ]


def test_autospec_target_is_the_real_function() -> None:
    """Guard the guard: the autospec above only enforces a signature if it's
    patching the real vector_store.hybrid_search."""
    assert tools.hybrid_search is hybrid_search
