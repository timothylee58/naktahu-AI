"""Tests for the SME Compliance Navigator (PatuhiKu) agent."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.sme_compliance_navigator.context import (
    AgentContext,
    get_context,
    list_domains,
)
from app.agents.sme_compliance_navigator.graph import build_sme_compliance_navigator_graph
from app.agents.sme_compliance_navigator.nodes import (
    _detect_domains,
    route_to_subagents,
    router_node,
    subagent_node,
    synthesizer_node,
)
from app.orchestration.adapters.sme_compliance_navigator import SMEComplianceNavigatorAdapter
from app.orchestration.context import OrchestratorContext
from app.orchestration.registry import _fallback_registry
from services.agent_registry import _fallback_registry as _flat_fallback_registry


# ── Knowledge context loader ────────────────────────────────────────────────


def test_list_domains_returns_all_three() -> None:
    assert list_domains() == ["corporate", "payroll", "tax"]


@pytest.mark.parametrize("domain", ["tax", "payroll", "corporate"])
def test_get_context_loads_real_knowledge_files(domain: str) -> None:
    ctx = get_context(domain)
    assert ctx.domain == domain
    assert ctx.review_cycle == "quarterly"
    assert ctx.sources, "every knowledge file declares at least one source URL"
    assert ctx.facts, "every knowledge file has bullet facts"
    assert "# " in ctx.content


def test_get_context_unknown_domain_raises() -> None:
    with pytest.raises(FileNotFoundError):
        get_context("nonexistent")


def test_is_stale_false_when_recent() -> None:
    ctx = AgentContext(domain="tax", as_of=date.today() - timedelta(days=10), sources=[], review_cycle="quarterly", content="x")
    assert ctx.is_stale() is False


def test_is_stale_true_past_120_days() -> None:
    ctx = AgentContext(domain="tax", as_of=date.today() - timedelta(days=121), sources=[], review_cycle="quarterly", content="x")
    assert ctx.is_stale() is True


def test_as_prompt_block_includes_staleness_note_when_stale() -> None:
    ctx = AgentContext(domain="tax", as_of=date.today() - timedelta(days=200), sources=["https://x"], review_cycle="quarterly", content="- fact one")
    block = ctx.as_prompt_block()
    assert "NOTE" in block
    assert "quarterly" in block


def test_as_prompt_block_omits_staleness_note_when_fresh() -> None:
    ctx = AgentContext(domain="tax", as_of=date.today(), sources=["https://x"], review_cycle="quarterly", content="- fact one")
    assert "NOTE" not in ctx.as_prompt_block()


def test_extract_facts_joins_wrapped_continuation_lines() -> None:
    from app.agents.sme_compliance_navigator.context import _extract_facts

    body = "- first fact\n  continues here\n- second fact"
    facts = _extract_facts(body)
    assert facts == ["first fact continues here", "second fact"]


# ── Router: multi-label domain classification ───────────────────────────────


def test_detect_domains_sdn_bhd_staff_and_revenue_triggers_all_three() -> None:
    profile = "I run a Sdn Bhd, 8 staff, RM400K revenue, hired 1 foreign worker last month"
    domains = _detect_domains(profile)
    assert set(domains) == {"tax", "payroll", "corporate"}


def test_detect_domains_payroll_only() -> None:
    domains = _detect_domains("I just hired a new employee, what EPF do I need to pay?")
    assert domains == ["payroll"]


def test_detect_domains_unclear_profile_defaults_to_all() -> None:
    domains = _detect_domains("help me with my business")
    assert set(domains) == {"tax", "payroll", "corporate"}


@pytest.mark.asyncio
async def test_router_node_sets_triggered_domains_and_resets_results() -> None:
    result = await router_node({"business_profile": "I have a Sdn Bhd"})
    assert result["triggered_domains"] == ["corporate"]
    assert result["domain_results"] == []


def test_route_to_subagents_builds_one_send_per_triggered_domain() -> None:
    sends = route_to_subagents({
        "triggered_domains": ["tax", "corporate"],
        "business_profile": "profile text",
        "language": "en",
    })
    assert len(sends) == 2
    assert {s.node for s in sends} == {"subagent_node"}
    assert {s.arg["domain"] for s in sends} == {"tax", "corporate"}
    assert all(s.arg["business_profile"] == "profile text" for s in sends)


# ── Subagent node ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subagent_node_calls_llm_with_domain_knowledge() -> None:
    with patch(
        "app.agents.sme_compliance_navigator.nodes.llm_complete",
        new=AsyncMock(return_value="File Form C within 7 months of financial year end"),
    ) as mock_llm:
        result = await subagent_node({"domain": "tax", "business_profile": "Sdn Bhd, RM400K revenue", "language": "en"})

    mock_llm.assert_awaited_once()
    domain_results = result["domain_results"]
    assert len(domain_results) == 1
    entry = domain_results[0]
    assert entry["domain"] == "tax"
    assert entry["label"] == "Tax (LHDN)"
    assert entry["reasoning"] == "File Form C within 7 months of financial year end"
    assert entry["facts"]
    assert entry["sources"]
    assert isinstance(entry["is_stale"], bool)


# ── Synthesizer: dedupe + prioritize + stale warnings ───────────────────────


@pytest.mark.asyncio
async def test_synthesizer_orders_corporate_before_tax_before_payroll() -> None:
    state = {
        "domain_results": [
            {"domain": "payroll", "label": "Payroll", "reasoning": "Register with SOCSO", "is_stale": False, "as_of": "2026-06-20"},
            {"domain": "tax", "label": "Tax", "reasoning": "File Form C", "is_stale": False, "as_of": "2026-06-20"},
            {"domain": "corporate", "label": "Corporate", "reasoning": "File annual return", "is_stale": False, "as_of": "2026-06-20"},
        ]
    }
    result = await synthesizer_node(state)
    assert [item["domain"] for item in result["checklist"]] == ["corporate", "tax", "payroll"]


@pytest.mark.asyncio
async def test_synthesizer_dedupes_near_identical_lines_across_domains() -> None:
    state = {
        "domain_results": [
            {"domain": "corporate", "label": "Corporate", "reasoning": "SSM registration required before hiring staff", "is_stale": False, "as_of": "2026-06-20"},
            {"domain": "payroll", "label": "Payroll", "reasoning": "SSM registration required before hiring staff\nRegister for EPF", "is_stale": False, "as_of": "2026-06-20"},
        ]
    }
    result = await synthesizer_node(state)
    items = [item["item"] for item in result["checklist"]]
    assert items.count("SSM registration required before hiring staff") == 1
    assert "Register for EPF" in items


@pytest.mark.asyncio
async def test_synthesizer_surfaces_stale_warning() -> None:
    state = {
        "domain_results": [
            {"domain": "tax", "label": "Tax (LHDN)", "reasoning": "File Form C", "is_stale": True, "as_of": "2025-01-01"},
        ]
    }
    result = await synthesizer_node(state)
    assert len(result["stale_warnings"]) == 1
    assert "Tax (LHDN)" in result["stale_warnings"][0]
    assert "2025-01-01" in result["stale_warnings"][0]


@pytest.mark.asyncio
async def test_synthesizer_no_stale_warning_when_fresh() -> None:
    state = {"domain_results": [{"domain": "tax", "label": "Tax", "reasoning": "File Form C", "is_stale": False, "as_of": "2026-06-20"}]}
    result = await synthesizer_node(state)
    assert result["stale_warnings"] == []


@pytest.mark.asyncio
async def test_synthesizer_empty_results_returns_empty_checklist() -> None:
    result = await synthesizer_node({"domain_results": []})
    assert result == {"checklist": [], "stale_warnings": []}


# ── Graph compilation + end-to-end fan-out ──────────────────────────────────


def test_graph_compiles() -> None:
    graph = build_sme_compliance_navigator_graph()
    compiled = graph.compile()
    assert compiled is not None


@pytest.mark.asyncio
async def test_graph_end_to_end_fans_out_to_triggered_domains_only() -> None:
    with patch(
        "app.agents.sme_compliance_navigator.nodes.llm_complete",
        new=AsyncMock(return_value="Some action item"),
    ):
        compiled = build_sme_compliance_navigator_graph().compile()
        result = await compiled.ainvoke({
            "business_profile": "I just hired a new employee, what EPF do I need to pay?",
            "language": "en",
            "domain_results": [],
        })

    assert result["triggered_domains"] == ["payroll"]
    assert len(result["domain_results"]) == 1
    assert result["domain_results"][0]["domain"] == "payroll"
    assert result["checklist"] == [{"domain": "payroll", "label": "Payroll (EPF/SOCSO/EIS)", "item": "Some action item"}]


# ── Registry ─────────────────────────────────────────────────────────────────


def test_enhanced_registry_fallback_includes_navigator() -> None:
    reg = _fallback_registry()
    assert "sme-compliance-navigator" in reg
    entry = reg["sme-compliance-navigator"]
    assert entry.plan_required == "free"
    assert entry.credit_cost == 1
    assert set(entry.supported_domains) == {"tax", "payroll", "corporate"}


def test_flat_registry_fallback_includes_navigator() -> None:
    reg = _flat_fallback_registry()
    assert "sme-compliance-navigator" in reg
    assert reg["sme-compliance-navigator"].credit_cost == 1


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_adapter_declares_expected_metadata() -> None:
    adapter = SMEComplianceNavigatorAdapter()
    assert adapter.name == "sme-compliance-navigator"
    assert adapter.plan_required == "free"
    assert adapter.credit_cost == 1
    assert set(adapter.supported_domains) == {"tax", "payroll", "corporate"}


@pytest.mark.asyncio
async def test_adapter_start_happy_path() -> None:
    adapter = SMEComplianceNavigatorAdapter()
    context = OrchestratorContext(
        query="I run a Sdn Bhd with 8 staff",
        language="en",
        session_id="sess-1",
        correlation_id="corr-1",
        extra={"business_profile": "I run a Sdn Bhd with 8 staff"},
    )

    fake_result = {
        "session_id": "sess-1",
        "checklist": [{"domain": "corporate", "label": "Corporate (SSM)", "item": "File annual return"}],
        "stale_warnings": [],
        "triggered_domains": ["corporate"],
    }
    with patch(
        "app.services.agent_runner.start_sme_compliance_navigator",
        new=AsyncMock(return_value=fake_result),
    ):
        result = await adapter.start(context)

    assert result.agent_name == "sme-compliance-navigator"
    assert result.status.value == "completed"
    assert "File annual return" in result.output
    assert result.structured_output["triggered_domains"] == ["corporate"]


@pytest.mark.asyncio
async def test_adapter_start_failure_returns_failed_status() -> None:
    adapter = SMEComplianceNavigatorAdapter()
    context = OrchestratorContext(
        query="test",
        language="en",
        session_id="sess-1",
        correlation_id="corr-1",
        extra={},
    )
    with patch(
        "app.services.agent_runner.start_sme_compliance_navigator",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await adapter.start(context)

    assert result.status.value == "failed"
    assert result.error == "boom"
