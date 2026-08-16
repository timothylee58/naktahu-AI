"""Tests for the Welfare Eligibility Agent (madani_scheme matching, migration 037)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.welfare_eligibility_agent.graph import build_welfare_eligibility_agent_graph
from app.agents.welfare_eligibility_agent.match_node import _rules_satisfied, match_node
from app.agents.welfare_eligibility_agent.synthesiser_node import synthesiser_node
from app.services.agent_runner import start_welfare_eligibility_agent
from app.orchestration.adapters.welfare_eligibility_agent import WelfareEligibilityAgentAdapter
from app.orchestration.context import OrchestratorContext
from app.orchestration.registry import _fallback_registry
from app.orchestration.types import AgentStatusEnum
from services.agent_registry import _fallback_registry as _flat_fallback_registry


# ── Deterministic rule matching ─────────────────────────────────────────────


def test_rules_satisfied_no_constraints_always_matches() -> None:
    ok, reasons = _rules_satisfied({}, {})
    assert ok is True
    assert reasons == []


def test_rules_satisfied_income_within_cap() -> None:
    ok, reasons = _rules_satisfied(
        {"max_household_income_myr": 5000},
        {"household_monthly_income_myr": 3000},
    )
    assert ok is True
    assert any("household income" in r for r in reasons)


def test_rules_satisfied_income_over_cap_rejects() -> None:
    ok, _ = _rules_satisfied(
        {"max_household_income_myr": 5000},
        {"household_monthly_income_myr": 8000},
    )
    assert ok is False


def test_rules_satisfied_missing_income_field_rejects_when_capped() -> None:
    # A capped scheme with no income data given can't be confirmed eligible —
    # must not default to "matches" on missing data.
    ok, _ = _rules_satisfied({"max_household_income_myr": 5000}, {})
    assert ok is False


def test_rules_satisfied_state_restricted() -> None:
    ok, _ = _rules_satisfied({"states": ["selangor", "penang"]}, {"state": "selangor"})
    assert ok is True
    ok, _ = _rules_satisfied({"states": ["selangor", "penang"]}, {"state": "johor"})
    assert ok is False


def test_rules_satisfied_requires_oku() -> None:
    ok, _ = _rules_satisfied({"requires_oku": True}, {"is_oku": False})
    assert ok is False
    ok, _ = _rules_satisfied({"requires_oku": True}, {"is_oku": True})
    assert ok is True


def test_rules_satisfied_min_dependents() -> None:
    ok, _ = _rules_satisfied({"min_dependents_children": 2}, {"dependents_children": 1})
    assert ok is False
    ok, _ = _rules_satisfied({"min_dependents_children": 2}, {"dependents_children": 3})
    assert ok is True


def test_rules_satisfied_employment_status_list() -> None:
    ok, _ = _rules_satisfied({"employment_status": ["unemployed"]}, {"employment_status": "employed"})
    assert ok is False
    ok, _ = _rules_satisfied({"employment_status": ["unemployed"]}, {"employment_status": "unemployed"})
    assert ok is True


# ── match_node — honest empty-table behaviour (migration 037 ships no rows) ─


@pytest.mark.asyncio
async def test_match_node_no_supabase_returns_no_schemes_loaded() -> None:
    result = await match_node({"profile": {}}, None)
    assert result == {"matched_schemes": [], "no_schemes_loaded": True}


@pytest.mark.asyncio
async def test_match_node_empty_table_returns_no_schemes_loaded() -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    result = await match_node({"profile": {}}, sb)
    assert result == {"matched_schemes": [], "no_schemes_loaded": True}


@pytest.mark.asyncio
async def test_match_node_fetch_exception_fails_open_to_no_schemes_loaded() -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("boom")
    result = await match_node({"profile": {}}, sb)
    assert result == {"matched_schemes": [], "no_schemes_loaded": True}


@pytest.mark.asyncio
async def test_match_node_matches_real_row_against_profile() -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[
        {
            "scheme_name": "Test Scheme",
            "category": "pendapatan",
            "scope": "federal",
            "description": "desc",
            "implementing_agency": "Test Agency",
            "eligibility_rules": {"max_household_income_myr": 5000},
            "source_url": "https://example.gov.my/scheme",
            "aggregator_url": "https://ihsanmadani.gov.my/inisiatif/pendapatan/test-scheme",
        },
    ])
    result = await match_node({"profile": {"household_monthly_income_myr": 2000, "state": "selangor"}}, sb)
    assert result["no_schemes_loaded"] is False
    assert len(result["matched_schemes"]) == 1
    assert result["matched_schemes"][0]["scheme_name"] == "Test Scheme"


@pytest.mark.asyncio
async def test_match_node_state_scoped_scheme_excludes_other_states() -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[
        {
            "scheme_name": "Selangor Scheme", "category": "kesihatan", "scope": "state:selangor",
            "description": "desc", "implementing_agency": "Agency", "eligibility_rules": {},
            "source_url": "https://example.gov.my", "aggregator_url": None,
        },
    ])
    result = await match_node({"profile": {"state": "johor"}}, sb)
    assert result["matched_schemes"] == []


# ── synthesiser_node — never invents a scheme name ──────────────────────────


@pytest.mark.asyncio
async def test_synthesiser_no_schemes_loaded_is_honest_not_fabricated() -> None:
    result = await synthesiser_node({"language": "en", "no_schemes_loaded": True, "matched_schemes": []})
    assert "hasn't been populated" in result["summary"]


@pytest.mark.asyncio
async def test_synthesiser_zero_matches_says_so() -> None:
    result = await synthesiser_node({"language": "en", "no_schemes_loaded": False, "matched_schemes": []})
    assert "no assistance schemes matched" in result["summary"]


@pytest.mark.asyncio
async def test_synthesiser_summarises_real_matches_via_llm() -> None:
    with patch(
        "app.agents.welfare_eligibility_agent.synthesiser_node.llm_complete",
        AsyncMock(return_value="You may qualify for Test Scheme."),
    ) as mock_llm:
        result = await synthesiser_node({
            "language": "en",
            "no_schemes_loaded": False,
            "matched_schemes": [{
                "scheme_name": "Test Scheme", "implementing_agency": "Agency",
                "description": "desc", "match_reasons": ["income within cap"],
                "source_url": "https://example.gov.my",
            }],
        })
        assert result["summary"] == "You may qualify for Test Scheme."
        mock_llm.assert_awaited_once()
        # The scheme's real name must be in the prompt given to the LLM —
        # it explains a real match, doesn't invent one from nothing.
        assert "Test Scheme" in mock_llm.call_args[0][1]


# ── Statelessness — privacy/page.tsx §2.4's explicit promise ───────────────
# Every other agent's start_* function in agent_runner.py logs its full
# input_payload to agent_runs via _log_run(). For this agent that payload
# is a demographic/income/disability profile, and it must NEVER reach
# Supabase — this is the regression guard for that specific property, not
# a generic "does it work" test.


@pytest.mark.asyncio
async def test_start_never_calls_log_run_with_sensitive_profile() -> None:
    sb = MagicMock()
    with patch(
        "app.services.agent_runner.get_welfare_eligibility_agent_graph"
    ) as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "matched_schemes": [], "no_schemes_loaded": True, "summary": "no schemes yet",
        })
        mock_get_graph.return_value = mock_graph

        await start_welfare_eligibility_agent(
            user_id="u1",
            payload={
                "language": "en", "birth_year": 1990, "household_monthly_income_myr": 2000,
                "is_oku": True, "state": "selangor",
            },
            supabase_client=sb,
            checkpointer=None,
        )

    # The only Supabase interaction allowed for this agent is match_node's
    # read of madani_scheme (via the graph, mocked out above) — nothing in
    # start_welfare_eligibility_agent itself should touch the client at all.
    sb.table.assert_not_called()


# ── Graph + registry wiring ──────────────────────────────────────────────────


def test_graph_compiles() -> None:
    graph = build_welfare_eligibility_agent_graph().compile()
    assert graph is not None


def test_registered_in_flat_registry_free_and_zero_credit() -> None:
    reg = _flat_fallback_registry()
    assert "welfare-eligibility-agent" in reg
    entry = reg["welfare-eligibility-agent"]
    assert entry.plan_required == "free"
    assert entry.credit_cost == 0


def test_registered_in_enhanced_registry() -> None:
    reg = _fallback_registry()
    assert "welfare-eligibility-agent" in reg
    entry = reg["welfare-eligibility-agent"]
    assert entry.supported_domains == ["welfare"]


# ── Adapter ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_adapter_start_happy_path() -> None:
    adapter = WelfareEligibilityAgentAdapter()
    context = OrchestratorContext(
        query="", language="en", domain="welfare",
        extra={"profile": {"state": "selangor"}, "supabase_client": None},
    )
    with patch(
        "app.services.agent_runner.start_welfare_eligibility_agent",
        AsyncMock(return_value={
            "session_id": "s1", "status": "completed",
            "summary": "no schemes yet", "matched_schemes": [], "no_schemes_loaded": True,
        }),
    ):
        result = await adapter.start(context)
    assert result.status == AgentStatusEnum.completed
    assert result.structured_output["no_schemes_loaded"] is True


@pytest.mark.asyncio
async def test_adapter_start_failure_returns_failed_status_not_raise() -> None:
    adapter = WelfareEligibilityAgentAdapter()
    context = OrchestratorContext(query="", language="en", domain="welfare", extra={})
    with patch(
        "app.services.agent_runner.start_welfare_eligibility_agent",
        AsyncMock(side_effect=Exception("db down")),
    ):
        result = await adapter.start(context)
    assert result.status == AgentStatusEnum.failed
    assert result.error == "db down"
