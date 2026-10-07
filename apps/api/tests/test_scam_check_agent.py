"""Tests for the ScamShield agent (official_gov_domains matching, migration 046)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.scam_check_agent.check_node import _extract_urls, _levenshtein, check_node
from app.agents.scam_check_agent.graph import build_scam_check_agent_graph
from app.agents.scam_check_agent.synthesiser_node import synthesiser_node
from app.services.agent_runner import start_scam_check_agent
from app.orchestration.adapters.scam_check_agent import ScamCheckAgentAdapter
from app.orchestration.context import OrchestratorContext
from app.orchestration.registry import _fallback_registry
from app.orchestration.types import AgentStatusEnum
from services.agent_registry import _fallback_registry as _flat_fallback_registry

_OFFICIAL_ROWS = [
    {"institution_name": "Inland Revenue Board (LHDN)", "domain": "hasil.gov.my"},
    {"institution_name": "Employees Provident Fund (EPF/KWSP)", "domain": "kwsp.gov.my"},
]


# ── URL extraction ───────────────────────────────────────────────────────────


def test_extract_urls_finds_bare_domain_no_scheme() -> None:
    urls = _extract_urls("Klik link ini: hasil-refund.gov.my.claim-now.cc/verify segera")
    assert "hasil-refund.gov.my.claim-now.cc" in urls


def test_extract_urls_finds_https_url_and_strips_www() -> None:
    urls = _extract_urls("Sila layari https://www.kwsp.gov.my/i-akaun untuk semak")
    assert "kwsp.gov.my" in urls


def test_extract_urls_ignores_plain_text_with_no_domain() -> None:
    urls = _extract_urls("Akaun EPF anda telah dikunci, sila hubungi kami.")
    assert urls == []


def test_extract_urls_deduplicates() -> None:
    urls = _extract_urls("hasil.gov.my and hasil.gov.my again")
    assert urls.count("hasil.gov.my") == 1


def test_extract_urls_resolves_userinfo_bait_to_real_host() -> None:
    """Regression test for a confirmed high-severity finding: a URL shaped
    like "https://hasil.gov.my@evil.com/verify" must resolve to the host a
    browser would actually connect to (evil.com), not the fake
    "username" (hasil.gov.my) an attacker put before the @ specifically to
    bait a naive domain check into reporting verified_official."""
    urls = _extract_urls("Sila sahkan: https://hasil.gov.my@evil.com/verify")
    assert urls == ["evil.com"]
    assert "hasil.gov.my" not in urls


def test_extract_urls_resolves_userinfo_bait_without_scheme() -> None:
    urls = _extract_urls("Sahkan di sini: hasil.gov.my@evil.com/verify segera")
    assert urls == ["evil.com"]


# ── Levenshtein (typosquat distance) ────────────────────────────────────────


def test_levenshtein_identical_strings_is_zero() -> None:
    assert _levenshtein("hasil.gov.my", "hasil.gov.my") == 0


def test_levenshtein_one_char_off_is_one() -> None:
    assert _levenshtein("hasii.gov.my", "hasil.gov.my") == 1


# ── check_node — deterministic verdicts, no LLM ─────────────────────────────


@pytest.mark.asyncio
async def test_check_node_no_url_found() -> None:
    result = await check_node({"input_text": "call me back please"}, None)
    assert result["overall_verdict"] == "no_url_found"
    assert result["checks"] == []


@pytest.mark.asyncio
async def test_check_node_no_supabase_still_reports_unverified_not_crash() -> None:
    result = await check_node({"input_text": "check hasil.gov.my please"}, None)
    assert result["overall_verdict"] == "unverified"
    assert result["checks"][0]["matched_institution"] is None


@pytest.mark.asyncio
async def test_check_node_exact_match_is_verified_official() -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=_OFFICIAL_ROWS)
    result = await check_node({"input_text": "Sila layari hasil.gov.my untuk semak status"}, sb)
    assert result["overall_verdict"] == "verified_official"
    assert result["checks"][0]["matched_institution"] == "Inland Revenue Board (LHDN)"


@pytest.mark.asyncio
async def test_check_node_typosquat_domain_is_impersonation_risk() -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=_OFFICIAL_ROWS)
    result = await check_node({"input_text": "Klik hasil-refund.gov.my.claim-now.cc untuk tuntut bayaran balik"}, sb)
    assert result["overall_verdict"] == "impersonation_risk"
    assert result["checks"][0]["matched_institution"] == "Inland Revenue Board (LHDN)"


@pytest.mark.asyncio
async def test_check_node_real_subdomain_of_official_is_verified_not_flagged() -> None:
    """Regression test for a confirmed high-severity finding: a real
    subdomain of an official institution's own domain (mytax.hasil.gov.my)
    must be verified_official, never impersonation_risk. The first version's
    substring check ("hasil" in domain) flagged exactly this."""
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=_OFFICIAL_ROWS)
    result = await check_node({"input_text": "Layari mytax.hasil.gov.my untuk e-Filing"}, sb)
    assert result["overall_verdict"] == "verified_official"
    assert result["checks"][0]["matched_institution"] == "Inland Revenue Board (LHDN)"


@pytest.mark.asyncio
async def test_check_node_unrelated_short_label_domain_not_falsely_flagged() -> None:
    """Regression test for a confirmed high-severity finding: a bare
    substring match falsely flagged unrelated domains that happen to
    contain a short official label — e.g. "pos" (pos.com.my's label) is a
    substring of "compose.com". The exact-component check must not match."""
    official_with_short_label = [{"institution_name": "Pos Malaysia", "domain": "pos.com.my"}]
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=official_with_short_label)
    result = await check_node({"input_text": "Check out compose.com for a deal"}, sb)
    assert result["overall_verdict"] == "unverified"
    assert result["checks"][0]["verdict"] != "impersonation_risk"


@pytest.mark.asyncio
async def test_check_node_unrelated_domain_is_unverified_not_safe() -> None:
    """A domain that's simply not on the list must never be reported as
    verified/safe — only 'unverified', the honest "we don't know" state."""
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=_OFFICIAL_ROWS)
    result = await check_node({"input_text": "Check out totally-unrelated-shop.com for a discount"}, sb)
    assert result["overall_verdict"] == "unverified"
    assert result["checks"][0]["verdict"] != "verified_official"


@pytest.mark.asyncio
async def test_check_node_fetch_exception_fails_open_to_unverified() -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.side_effect = Exception("boom")
    result = await check_node({"input_text": "check hasil.gov.my"}, sb)
    assert result["checks"][0]["verdict"] == "unverified"


@pytest.mark.asyncio
async def test_check_node_overall_verdict_is_worst_case_across_multiple_urls() -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=_OFFICIAL_ROWS)
    result = await check_node(
        {"input_text": "Real: hasil.gov.my Fake: hasil-refund.gov.my.claim-now.cc"}, sb
    )
    assert result["overall_verdict"] == "impersonation_risk"


@pytest.mark.asyncio
async def test_check_node_detects_urgency_and_payment_red_flags() -> None:
    result = await check_node(
        {"input_text": "URGENT: your account will be suspended, click link and provide OTP now"}, None
    )
    assert "urgency_language" in result["text_red_flags"]
    assert "requests_payment_or_otp" in result["text_red_flags"]


@pytest.mark.asyncio
async def test_check_node_no_red_flags_for_plain_text() -> None:
    result = await check_node({"input_text": "Just checking if this is real, thanks."}, None)
    assert result["text_red_flags"] == []


# ── synthesiser_node — never overrides the verdict ──────────────────────────


@pytest.mark.asyncio
async def test_synthesiser_no_url_found_is_honest() -> None:
    result = await synthesiser_node({"language": "en", "overall_verdict": "no_url_found", "checks": [], "text_red_flags": []})
    assert "No link was detected" in result["summary"]


@pytest.mark.asyncio
async def test_synthesiser_summarises_verdict_via_llm() -> None:
    with patch(
        "app.agents.scam_check_agent.synthesiser_node.llm_complete",
        AsyncMock(return_value="This link mimics LHDN. Do not click it."),
    ) as mock_llm:
        result = await synthesiser_node({
            "language": "en",
            "overall_verdict": "impersonation_risk",
            "checks": [{
                "url": "hasil-refund.gov.my.claim-now.cc", "domain": "hasil-refund.gov.my.claim-now.cc",
                "verdict": "impersonation_risk", "matched_institution": "Inland Revenue Board (LHDN)",
                "matched_domain": "hasil.gov.my",
            }],
            "text_red_flags": ["urgency_language"],
        })
        assert result["summary"] == "This link mimics LHDN. Do not click it."
        mock_llm.assert_awaited_once()
        # The real verdict facts must be in the prompt given to the LLM.
        assert "impersonation_risk" in mock_llm.call_args[0][1]


@pytest.mark.asyncio
async def test_synthesiser_falls_back_to_raw_facts_when_llm_empty() -> None:
    with patch("app.agents.scam_check_agent.synthesiser_node.llm_complete", AsyncMock(return_value="")):
        result = await synthesiser_node({
            "language": "en",
            "overall_verdict": "verified_official",
            "checks": [{"url": "hasil.gov.my", "domain": "hasil.gov.my", "verdict": "verified_official", "matched_institution": "LHDN", "matched_domain": "hasil.gov.my"}],
            "text_red_flags": [],
        })
        assert "verified_official" in result["summary"]


# ── Statelessness — same privacy reasoning as welfare_eligibility_agent ────


@pytest.mark.asyncio
async def test_start_never_calls_log_run_with_pasted_text() -> None:
    sb = MagicMock()
    with patch("app.services.agent_runner.get_scam_check_agent_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "checks": [], "overall_verdict": "no_url_found", "text_red_flags": [], "summary": "no link found",
        })
        mock_get_graph.return_value = mock_graph

        await start_scam_check_agent(
            user_id="u1",
            payload={"language": "en", "input_text": "call from someone claiming to be LHDN"},
            supabase_client=sb,
            checkpointer=None,
        )

    sb.table.assert_not_called()


# ── Graph + registry wiring ──────────────────────────────────────────────────


def test_graph_compiles() -> None:
    graph = build_scam_check_agent_graph().compile()
    assert graph is not None


def test_registered_in_flat_registry_free_and_zero_credit() -> None:
    reg = _flat_fallback_registry()
    assert "scam-check-agent" in reg
    entry = reg["scam-check-agent"]
    assert entry.plan_required == "free"
    assert entry.credit_cost == 0


def test_registered_in_enhanced_registry() -> None:
    reg = _fallback_registry()
    assert "scam-check-agent" in reg
    entry = reg["scam-check-agent"]
    assert entry.supported_domains == ["scam_check"]


# ── Adapter ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_adapter_start_happy_path() -> None:
    adapter = ScamCheckAgentAdapter()
    context = OrchestratorContext(
        query="is hasil.gov.my real", language="en", domain="scam_check",
        extra={"supabase_client": None},
    )
    with patch(
        "app.services.agent_runner.start_scam_check_agent",
        AsyncMock(return_value={
            "session_id": "s1", "status": "completed",
            "summary": "verified", "checks": [], "overall_verdict": "verified_official", "text_red_flags": [],
        }),
    ) as mock_start:
        result = await adapter.start(context)
    assert result.status == AgentStatusEnum.completed
    assert result.structured_output["overall_verdict"] == "verified_official"
    # Regression guard: the pasted text must come from context.query, not
    # context.extra — confirmed bug where extra never carried input_text.
    assert mock_start.call_args.kwargs["payload"]["input_text"] == "is hasil.gov.my real"


@pytest.mark.asyncio
async def test_adapter_start_failure_returns_failed_status_not_raise() -> None:
    adapter = ScamCheckAgentAdapter()
    context = OrchestratorContext(query="", language="en", domain="scam_check", extra={})
    with patch(
        "app.services.agent_runner.start_scam_check_agent",
        AsyncMock(side_effect=Exception("db down")),
    ):
        result = await adapter.start(context)
    assert result.status == AgentStatusEnum.failed
    assert result.error == "db down"
