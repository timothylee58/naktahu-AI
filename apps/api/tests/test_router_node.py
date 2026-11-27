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
def _reset_schema_rejection_latch(monkeypatch: pytest.MonkeyPatch):
    """The rejection cooldown is module state; without a reset one test would silence the next."""
    monkeypatch.setattr("app.agents.router_node._schema_rejected_until", 0.0)


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
async def test_router_node_overrides_llm_when_it_mislabels_english_as_bm() -> None:
    """The production bug: the classifier returned language="bm" for this
    plain English query (router_classified log, 2026-10-08), so the
    synthesiser answered in Bahasa Malaysia. The query's own words win."""
    completion = _mock_completion('{"language": "bm", "domain": "welfare", "intent": "report lost MyKad"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "What should I do if I lose my MyKad?"})

    assert result["language"] == "en"


@pytest.mark.asyncio
async def test_router_node_overrides_llm_when_it_mislabels_bm_as_en() -> None:
    completion = _mock_completion('{"language": "en", "domain": "government", "intent": "replace MyKad"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "Bagaimana nak tukar MyKad yang hilang?"})

    assert result["language"] == "bm"


@pytest.mark.asyncio
async def test_router_node_keeps_llm_language_when_query_is_ambiguous() -> None:
    """Content words only (no function words to vote on): no override."""
    completion = _mock_completion('{"language": "bm", "domain": "government", "intent": "mykad"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "MyKad"})

    assert result["language"] == "bm"


@pytest.mark.asyncio
async def test_router_node_detects_bm_even_when_the_llm_call_fails() -> None:
    """Previously any LLM failure meant language="en" no matter what the
    user wrote, so a Malay question got an English answer."""
    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("timeout"))
        result = await router_node({"query": "Berapa kadar cukai pendapatan saya?"})

    assert result["language"] == "bm"


@pytest.mark.asyncio
async def test_router_node_cjk_still_wins_over_everything() -> None:
    completion = _mock_completion('{"language": "bm", "domain": "government", "intent": "mykad"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "如果我遗失了 MyKad 怎么办？ What should I do?"})

    assert result["language"] == "zh"


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


# ── scam_check is never offered to the general chat classifier ─────────────
# Regression test for a confirmed high-severity finding: scam_check is a
# valid domain for scam-check-agent (its own dedicated single-shot
# endpoint), but must NEVER be something general /chat queries get
# classified into — that path skips check_node.py's deterministic
# verification entirely and would let the general RAG synthesiser imply a
# link is safe/fake without ever checking official_gov_domains.


def test_router_node_never_offers_scam_check_to_the_llm_classifier() -> None:
    assert "scam_check" not in _SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_router_node_rejects_scam_check_even_if_llm_outputs_it_anyway() -> None:
    """Defense in depth: even if a model somehow outputs domain="scam_check"
    despite never being told it's an option, it's not in _VALID_DOMAINS for
    router_node's purposes — falls back to None (search-everything) like any
    other unrecognised domain, never leaks through as a real classification."""
    completion = _mock_completion(
        '{"language": "en", "domain": "scam_check", "intent": "is this link real"}'
    )

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=completion)
        result = await router_node({"query": "is this LHDN link real?"})

    assert result["domain"] is None


@pytest.mark.asyncio
async def test_router_retries_with_larger_budget_when_first_reply_is_unparseable() -> None:
    truncated = _mock_completion('{"language": "en", "domain": "bus')
    full = _mock_completion('{"language": "en", "domain": "business", "intent": "register company SSM"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        create = AsyncMock(side_effect=[truncated, full])
        mock_client.chat.completions.create = create
        result = await router_node({"query": "How do I register a Sdn Bhd with SSM?"})

    assert result["domain"] == "business"
    assert result["intent"] == "register company SSM"
    assert [c.kwargs["max_tokens"] for c in create.await_args_list] == [128, 384]


@pytest.mark.asyncio
async def test_router_makes_one_call_when_first_reply_parses() -> None:
    ok = _mock_completion('{"language": "en", "domain": "tax", "intent": "income tax rate"}')

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        create = AsyncMock(return_value=ok)
        mock_client.chat.completions.create = create
        await router_node({"query": "What is the income tax rate?"})

    assert create.await_count == 1


@pytest.mark.asyncio
async def test_router_leaves_domain_unset_when_both_attempts_are_unparseable() -> None:
    junk = _mock_completion("I cannot classify this.")

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        create = AsyncMock(return_value=junk)
        mock_client.chat.completions.create = create
        result = await router_node({"query": "How do I register a Sdn Bhd with SSM?"})

    assert result["domain"] is None
    assert create.await_count == 2


# ── ROUTER_STRUCTURED_MODE: structured paths with the prompt-and-parse fallback ──


_STRUCTURED_RESULT = {
    "language": "bm",
    "domain": "tax",
    "intent": "kadar cukai pendapatan",
    "is_live_status_query": False,
    "place_name": None,
    "is_structured_parliament_query": False,
    "parliament_bill_number": None,
    "parliament_mp_query": None,
}


def _claude_response(tool_input: dict | None) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use" if tool_input is not None else "text"
    block.input = tool_input
    resp = MagicMock()
    resp.content = [block]
    return resp


@pytest.mark.asyncio
async def test_default_mode_sends_no_structured_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ROUTER_STRUCTURED_MODE", raising=False)
    create = AsyncMock(return_value=_mock_completion('{"language": "en", "domain": "tax", "intent": "x"}'))

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = create
        await router_node({"query": "How much is income tax?"})

    assert "response_format" not in create.call_args.kwargs


@pytest.mark.asyncio
async def test_ilmu_schema_mode_sends_strict_schema_and_uses_result(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "ilmu_schema")
    create = AsyncMock(return_value=_mock_completion(json.dumps(_STRUCTURED_RESULT)))

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = create
        result = await router_node({"query": "Berapa kadar cukai pendapatan saya?"})

    rf = create.call_args.kwargs["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert "scam_check" not in rf["json_schema"]["schema"]["properties"]["domain"]["enum"]
    assert create.await_count == 1
    assert result["domain"] == "tax"


@pytest.mark.asyncio
async def test_ilmu_schema_rejection_falls_back_to_plain_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    """ILMU 400s on response_format -> same call without it, parsed by extract_json_object."""
    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "ilmu_schema")
    plain = _mock_completion('{"language": "en", "domain": "finance", "intent": "loan"}')
    create = AsyncMock(side_effect=[RuntimeError("response_format not supported"), plain])

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = create
        result = await router_node({"query": "How do I apply for a loan?"})

    assert create.await_count == 2
    assert "response_format" not in create.call_args_list[1].kwargs
    assert result["domain"] == "finance"


@pytest.mark.asyncio
async def test_ilmu_schema_empty_output_falls_back_to_plain_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "ilmu_schema")
    plain = _mock_completion('{"language": "en", "domain": "legal", "intent": "tenancy"}')
    create = AsyncMock(side_effect=[_mock_completion("not json at all"), plain])

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = create
        result = await router_node({"query": "Can my landlord evict me?"})

    assert result["domain"] == "legal"


@pytest.mark.asyncio
async def test_claude_tool_mode_forces_tool_and_skips_ilmu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "claude_tool")
    claude_create = AsyncMock(return_value=_claude_response(_STRUCTURED_RESULT))
    ilmu_create = AsyncMock()

    with patch("app.agents.router_node.anthropic_client") as mock_claude, patch(
        "app.agents.router_node.ilmu_client"
    ) as mock_ilmu:
        mock_claude.messages.create = claude_create
        mock_ilmu.chat.completions.create = ilmu_create
        result = await router_node({"query": "Berapa kadar cukai pendapatan saya?"})

    kwargs = claude_create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "classify_query"}
    assert kwargs["tools"][0]["input_schema"]["additionalProperties"] is False
    ilmu_create.assert_not_awaited()
    assert result["domain"] == "tax"


@pytest.mark.asyncio
@pytest.mark.parametrize("claude_outcome", ["error", "no_tool_block"])
async def test_claude_tool_failure_falls_back_to_ilmu_plain_parser(
    monkeypatch: pytest.MonkeyPatch, claude_outcome: str
) -> None:
    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "claude_tool")
    if claude_outcome == "error":
        claude_create = AsyncMock(side_effect=RuntimeError("anthropic 529"))
    else:
        claude_create = AsyncMock(return_value=_claude_response(None))
    plain = _mock_completion('{"language": "en", "domain": "government", "intent": "ssm"}')

    with patch("app.agents.router_node.anthropic_client") as mock_claude, patch(
        "app.agents.router_node.ilmu_client"
    ) as mock_ilmu:
        mock_claude.messages.create = claude_create
        mock_ilmu.chat.completions.create = AsyncMock(return_value=plain)
        result = await router_node({"query": "How do I register a company with SSM?"})

    assert result["domain"] == "government"


@pytest.mark.asyncio
async def test_unknown_mode_value_behaves_as_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "banana")
    create = AsyncMock(return_value=_mock_completion('{"language": "en", "domain": "tax", "intent": "x"}'))

    with patch("app.agents.router_node.ilmu_client") as mock_client:
        mock_client.chat.completions.create = create
        await router_node({"query": "How much is income tax?"})

    assert "response_format" not in create.call_args.kwargs


def _status_error(status: int) -> Exception:
    import httpx
    import openai

    request = httpx.Request("POST", "https://api.ilmu.ai/v1/chat/completions")
    return openai.APIStatusError(
        "response_format unsupported", response=httpx.Response(status, request=request), body=None
    )


@pytest.mark.asyncio
async def test_schema_rejection_never_trips_the_shared_ilmu_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qodo finding: five deterministic 400s on response_format used to open ilmu_breaker, which
    the plain fallback and guard_node share, taking classification down entirely."""
    from app.orchestration.circuit_breaker import CircuitBreaker, CircuitState

    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "ilmu_schema")
    breaker = CircuitBreaker("ilmu-test", failure_threshold=5)
    plain = _mock_completion('{"language": "en", "domain": "tax", "intent": "x"}')

    async def create(**kwargs: object) -> MagicMock:
        if "response_format" in kwargs:
            raise _status_error(400)
        return plain

    with patch("app.agents.router_node.ilmu_breaker", breaker), patch(
        "app.agents.router_node.ilmu_client"
    ) as mock_client:
        mock_client.chat.completions.create = AsyncMock(side_effect=create)
        for _ in range(8):
            result = await router_node({"query": "How much is income tax?"})
        calls = mock_client.chat.completions.create.call_args_list

    assert breaker.state == CircuitState.closed
    assert result["domain"] == "tax"
    structured_calls = [c for c in calls if "response_format" in c.kwargs]
    assert len(structured_calls) == 1  # cooldown stops re-sending a format ILMU already refused


@pytest.mark.asyncio
async def test_non_rejection_errors_still_count_against_the_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 5xx is a real outage signal; only 400/404/422 are treated as 'format unsupported'."""
    from app.orchestration.circuit_breaker import CircuitBreaker

    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "ilmu_schema")
    breaker = CircuitBreaker("ilmu-test", failure_threshold=5)
    plain = _mock_completion('{"language": "en", "domain": "tax", "intent": "x"}')

    async def create(**kwargs: object) -> MagicMock:
        if "response_format" in kwargs:
            raise _status_error(503)
        return plain

    with patch("app.agents.router_node.ilmu_breaker", breaker), patch(
        "app.agents.router_node.ilmu_client"
    ) as mock_client:
        mock_client.chat.completions.create = AsyncMock(side_effect=create)
        await router_node({"query": "How much is income tax?"})

    assert breaker.metrics["total_failures"] == 1


@pytest.mark.asyncio
async def test_open_anthropic_breaker_skips_claude_and_falls_back_to_ilmu(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.orchestration.circuit_breaker import CircuitBreaker

    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "claude_tool")
    breaker = CircuitBreaker("anthropic-test", failure_threshold=1)
    breaker._record_failure()
    claude_create = AsyncMock()
    plain = _mock_completion('{"language": "en", "domain": "government", "intent": "ssm"}')

    with patch("app.agents.router_node.anthropic_breaker", breaker), patch(
        "app.agents.router_node.anthropic_client"
    ) as mock_claude, patch("app.agents.router_node.ilmu_client") as mock_ilmu:
        mock_claude.messages.create = claude_create
        mock_ilmu.chat.completions.create = AsyncMock(return_value=plain)
        result = await router_node({"query": "How do I register a company with SSM?"})

    claude_create.assert_not_awaited()
    assert result["domain"] == "government"


@pytest.mark.asyncio
async def test_claude_tool_call_has_a_timeout_and_honours_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTER_STRUCTURED_MODE", "claude_tool")
    monkeypatch.setenv("ROUTER_CLAUDE_MODEL", "claude-test-model")
    claude_create = AsyncMock(return_value=_claude_response(_STRUCTURED_RESULT))

    with patch("app.agents.router_node.anthropic_client") as mock_claude:
        mock_claude.messages.create = claude_create
        await router_node({"query": "Berapa kadar cukai pendapatan saya?"})

    assert claude_create.call_args.kwargs["timeout"] > 0
    assert claude_create.call_args.kwargs["model"] == "claude-test-model"


def test_router_node_keeps_its_weave_trace_and_the_env_lookup_does_not() -> None:
    """Qodo finding: _structured_mode was inserted between @weave.op() and router_node."""
    import inspect

    import app.agents.router_node as mod

    source = inspect.getsource(mod)
    assert "@weave.op()\nasync def router_node" in source
    assert "@weave.op()\ndef _structured_mode" not in source
