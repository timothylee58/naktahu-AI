"""Tests for app.agents.router_node."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.router_node import router_node


def _mock_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_router_node_bm_finance() -> None:
    """BM query about tax should be classified as bm + finance."""
    completion = _mock_completion('{"language": "bm", "domain": "finance", "intent": "cukai pendapatan individu"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "Berapa kadar cukai pendapatan saya?"})

    assert result["language"] == "bm"
    assert result["domain"] == "finance"


@pytest.mark.asyncio
async def test_router_node_en_government() -> None:
    """English query about SSM classified as en + government."""
    completion = _mock_completion('{"language": "en", "domain": "government", "intent": "register company SSM"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "How do I register a company with SSM?"})

    assert result["language"] == "en"
    assert result["domain"] == "government"


@pytest.mark.asyncio
async def test_router_node_defaults_on_parse_error() -> None:
    """Malformed JSON from model → defaults to en + government."""
    completion = _mock_completion("not json at all")

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "What?"})

    assert result["language"] == "en"
    assert result["domain"] == "government"


@pytest.mark.asyncio
async def test_router_node_defaults_on_exception() -> None:
    """API exception → defaults to en + government without raising."""
    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("timeout"))
        result = await router_node({"query": "Something"})

    assert result["language"] == "en"
    assert result["domain"] == "government"


@pytest.mark.asyncio
async def test_router_node_invalid_domain_coerced() -> None:
    """Unknown domain value → coerced to government."""
    completion = _mock_completion('{"language": "en", "domain": "sports", "intent": "football"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "Football result"})

    assert result["domain"] == "government"


@pytest.mark.asyncio
async def test_router_node_json_in_markdown_fence() -> None:
    """JSON wrapped in markdown fences is extracted correctly."""
    content = '```json\n{"language": "bm", "domain": "health", "intent": "hospital services"}\n```'
    completion = _mock_completion(content)

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "Perkhidmatan hospital awam"})

    assert result["language"] == "bm"
    assert result["domain"] == "healthcare"
