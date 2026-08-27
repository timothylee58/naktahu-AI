"""Tests for app.agents.router_node."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.router_node import _DOMAIN_ALIASES, _SYSTEM_PROMPT, _VALID_DOMAINS, router_node


def _mock_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.fixture(autouse=True)
def _default_query_already_seen():
    """Every test in this file except the speculative-embed tests below
    (which override this explicitly) shouldn't fire a real background
    embedding task — has_query_been_seen defaults to True here so
    router_node's speculative-embed branch is a no-op unless a test
    deliberately asks for it."""
    with patch("app.agents.router_node.cache_svc.has_query_been_seen", new=AsyncMock(return_value=True)):
        yield


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
async def test_router_node_fires_speculative_embed_when_query_never_seen() -> None:
    """cache.has_query_been_seen()==False guarantees rag_node's real cache
    lookup will also miss (see cache.mark_query_seen's docstring) — so
    router_node must fire the speculative embed and hand it to rag_node
    via state, in parallel with its own classify call."""
    completion = _mock_completion('{"language": "en", "domain": "tax", "intent": "test"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client, \
         patch("app.agents.router_node.cache_svc.has_query_been_seen", new=AsyncMock(return_value=False)), \
         patch("app.agents.rag_node._embed", new=AsyncMock(return_value=[0.1, 0.2])) as mock_embed:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "How do I pay income tax?"})

    task = result["_speculative_embedding_task"]
    assert task is not None
    embedding = await task
    assert embedding == [0.1, 0.2]
    mock_embed.assert_awaited_once_with("How do I pay income tax?")


@pytest.mark.asyncio
async def test_router_node_skips_speculative_embed_when_query_already_seen() -> None:
    """A query text that's already cached under some domain/language must
    never trigger a speculative embed — it would either be wasted (real
    lookup also hits) or, in the rare reclassification case, no worse than
    today's behaviour. Either way, firing it here has no guaranteed payoff,
    unlike the never-seen case."""
    completion = _mock_completion('{"language": "en", "domain": "tax", "intent": "test"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client, \
         patch("app.agents.router_node.cache_svc.has_query_been_seen", new=AsyncMock(return_value=True)), \
         patch("app.agents.rag_node._embed", new=AsyncMock()) as mock_embed:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "How do I pay income tax?"})

    assert result["_speculative_embedding_task"] is None
    mock_embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_router_node_skips_speculative_embed_for_empty_query() -> None:
    completion = _mock_completion('{"language": "en", "domain": null, "intent": "test"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client, \
         patch("app.agents.router_node.cache_svc.has_query_been_seen", new=AsyncMock()) as mock_seen:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": ""})

    assert result["_speculative_embedding_task"] is None
    mock_seen.assert_not_awaited()  # no point checking the marker for an empty query


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


@pytest.mark.asyncio
async def test_router_node_property_domain_classified() -> None:
    """'property' was added to _VALID_DOMAINS/prompt/DB constraint in
    migration 030 — same reachability regression class as the parliament
    test above."""
    completion = _mock_completion(
        '{"language": "en", "domain": "property", "intent": "check land title status"}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "How do I check my land title status?"})

    assert result["domain"] == "property"


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("eis", "epf"),
        ("socso", "epf"),
        ("perkeso", "epf"),
        ("tanah", "property"),
        ("hartanah", "property"),
        ("e-tanah", "property"),
        ("strata", "property"),
        ("sewa", "property"),
    ],
)
def test_domain_aliases_map_to_canonical_domain(alias: str, expected: str) -> None:
    """EIS/SOCSO/Perkeso terms fold to 'epf' (registration/contribution
    facts); property-related BM/EN terms fold to 'property' — per the
    domain split decided when migration 030 added the property domain."""
    assert _DOMAIN_ALIASES[alias] == expected


@pytest.mark.asyncio
async def test_router_node_detects_live_status_query() -> None:
    """Warung Watch: router_node's single classification call also flags
    live "is X packed right now" queries and extracts the place name."""
    completion = _mock_completion(
        '{"language": "en", "domain": "business", "intent": "check if Pelita is busy", '
        '"is_live_status_query": true, "place_name": "Pelita"}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "Is Pelita packed right now?"})

    assert result["is_live_status_query"] is True
    assert result["place_name"] == "Pelita"


@pytest.mark.asyncio
async def test_router_node_normal_query_not_flagged_as_live_status() -> None:
    completion = _mock_completion(
        '{"language": "en", "domain": "epf", "intent": "epf withdrawal age"}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "What is the EPF withdrawal age?"})

    assert result["is_live_status_query"] is False
    assert result["place_name"] is None


@pytest.mark.asyncio
async def test_router_node_ignores_flag_true_without_usable_place_name() -> None:
    """A malformed classification (flag true, no name / empty name) can't
    be routed to warung_watch_node — falls back to the normal RAG path
    rather than crashing on an unusable place_name."""
    completion = _mock_completion(
        '{"language": "en", "domain": "business", "intent": "vague busy question", '
        '"is_live_status_query": true, "place_name": "  "}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "is it busy"})

    assert result["is_live_status_query"] is False
    assert result["place_name"] is None


# ── structured parliament lookup classification ─────────────────────────────

@pytest.mark.asyncio
async def test_router_node_classifies_bill_vote_query_as_structured() -> None:
    completion = _mock_completion(
        '{"language": "en", "domain": "parliament", "intent": "bill vote record", '
        '"is_structured_parliament_query": true, "parliament_bill_number": "RUU 355", '
        '"parliament_mp_query": null}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "How did MPs vote on RUU 355?"})

    assert result["is_structured_parliament_query"] is True
    assert result["parliament_bill_number"] == "RUU 355"
    assert result["parliament_mp_query"] is None


@pytest.mark.asyncio
async def test_router_node_classifies_mp_lookup_query_as_structured() -> None:
    completion = _mock_completion(
        '{"language": "en", "domain": "parliament", "intent": "who is the mp", '
        '"is_structured_parliament_query": true, "parliament_bill_number": null, '
        '"parliament_mp_query": "Bangi"}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "Who is the MP for Bangi?"})

    assert result["is_structured_parliament_query"] is True
    assert result["parliament_mp_query"] == "Bangi"
    assert result["parliament_bill_number"] is None


@pytest.mark.asyncio
async def test_router_node_leaves_general_hansard_question_unstructured() -> None:
    """General debate-content questions stay on the normal RAG path — only
    a specific bill/MP lookup should short-circuit to parliament_query_node."""
    completion = _mock_completion(
        '{"language": "en", "domain": "parliament", "intent": "tax reform debate", '
        '"is_structured_parliament_query": false, "parliament_bill_number": null, '
        '"parliament_mp_query": null}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "What did parliament debate about tax reform?"})

    assert result["is_structured_parliament_query"] is False
    assert result["parliament_bill_number"] is None
    assert result["parliament_mp_query"] is None


@pytest.mark.asyncio
async def test_router_node_ignores_structured_flag_true_without_usable_entity() -> None:
    """A malformed classification (flag true, both entities null/blank)
    can't be routed to parliament_query_node — falls back to RAG."""
    completion = _mock_completion(
        '{"language": "en", "domain": "parliament", "intent": "vague", '
        '"is_structured_parliament_query": true, "parliament_bill_number": "  ", '
        '"parliament_mp_query": null}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "tell me about parliament"})

    assert result["is_structured_parliament_query"] is False
    assert result["parliament_bill_number"] is None
    assert result["parliament_mp_query"] is None
