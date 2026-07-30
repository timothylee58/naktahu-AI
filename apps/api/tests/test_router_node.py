"""Tests for app.agents.router_node."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.router_node import _SYSTEM_PROMPT, _VALID_DOMAINS, router_node


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
    """Malformed JSON from model → language defaults to en, domain is
    unset (None) rather than a specific domain — hybrid_search treats
    None as search-everything, which is the correct fallback when
    classification fails. Defaulting to a specific domain risks silently
    confining retrieval to whichever domain is currently empty (it has
    happened with "government" — CLAUDE.md Trap #6)."""
    completion = _mock_completion("not json at all")

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "What?"})

    assert result["language"] == "en"
    assert result["domain"] is None


@pytest.mark.asyncio
async def test_router_node_defaults_on_exception() -> None:
    """API exception → language defaults to en, domain stays unset (None)
    rather than falling back to a specific domain."""
    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("timeout"))
        result = await router_node({"query": "Something"})

    assert result["language"] == "en"
    assert result["domain"] is None


@pytest.mark.asyncio
async def test_router_node_invalid_domain_coerced() -> None:
    """Unknown domain value → coerced to None (search everything), not a
    specific domain the model never actually claimed."""
    completion = _mock_completion('{"language": "en", "domain": "sports", "intent": "football"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "Football result"})

    assert result["domain"] is None


@pytest.mark.asyncio
async def test_router_node_non_string_domain_does_not_crash() -> None:
    """A malformed LLM response with a list/dict for "domain" must not
    raise TypeError from _DOMAIN_ALIASES.get(domain, domain) — dicts
    require hashable keys, and a list/dict domain value isn't one."""
    completion = _mock_completion('{"language": "en", "domain": ["tax", "epf"], "intent": "x"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "Something"})

    assert result["domain"] is None


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


@pytest.mark.asyncio
async def test_router_node_json_with_trailing_commentary_containing_brace() -> None:
    """Regression: a naive greedy regex (r'\\{.*\\}') matches from the first
    '{' to the LAST '}' anywhere in the completion, so if the model appends
    ANY trailing text containing a brace, the match spans past the actual
    JSON object and json.loads fails with "Extra data" — silently
    discarding an otherwise-correct classification and falling back to
    domain=None. router_node now uses extract_json_object() (JSONDecoder.
    raw_decode from the first '{'), which parses only the first balanced
    object and ignores anything after it."""
    content = (
        '{"language": "en", "domain": "government", "intent": "register company SSM"} '
        "Let me know if you need more info {happy to help}"
    )
    completion = _mock_completion(content)

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "How do I register a company with SSM?"})

    assert result["language"] == "en"
    assert result["domain"] == "government"


@pytest.mark.asyncio
async def test_router_node_parliament_domain_classified() -> None:
    """'parliament' must be a reachable classification — it was added to
    _VALID_DOMAINS in the hansard->parliament rename, but the LLM
    classifier's own system prompt text never listed it as an option,
    so the model could never actually choose it. Regression for that
    prompt/domain-list drift (a 4th site beyond what Trap #6 tracks:
    a hardcoded domain list embedded in a prompt string, not just a
    Python set/DB constraint)."""
    completion = _mock_completion(
        '{"language": "en", "domain": "parliament", "intent": "find MP contact"}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node(
            {"query": "Who is the Member of Parliament for my constituency?"}
        )

    assert result["domain"] == "parliament"


def test_system_prompt_lists_every_valid_domain() -> None:
    """The classifier can only choose a domain the prompt text tells it
    about. Regression guard against the exact drift that made 'parliament'
    unreachable: _VALID_DOMAINS was updated in the rename but the prompt's
    own domain-list sentence was not. Every domain in _VALID_DOMAINS must
    appear in the prompt text, not just in the Python set."""
    for domain in _VALID_DOMAINS:
        assert domain in _SYSTEM_PROMPT, f"{domain!r} missing from router_node._SYSTEM_PROMPT"
