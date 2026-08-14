"""tests/test_grant_draft_generator.py

Unit tests for the Grant Draft Generator agent: node behaviour (grant
lookup found/not-found, section drafting, financial-skeleton disclaimer),
export (PDF light-path, DOCX round-trip), and credit-exemption/timing
(business plan unlimited, non-business plan billed at confirm not start).
"""
from __future__ import annotations

import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.grant_draft_generator.nodes import (
    compile_node,
    draft_node,
    fetch_grant_node,
    generate_export_node,
)
from app.agents.grant_draft_generator.state import GrantDraftState
from app.agents.tools import generate_docx

SAMPLE_GRANT: dict[str, Any] = {
    "programme_name": "SME Digitalization Grant (SDMG)",
    "agency": "MDEC",
    "grant_type": "matching_grant",
    "amount_min_myr": 1000,
    "amount_max_myr": 5000,
    "eligible_sectors": ["retail", "services"],
    "notes_en": "Matching grant for digitalisation tools.",
    "notes_bm": "Geran padanan untuk alat pendigitalan.",
}

BUSINESS_PROFILE: dict[str, Any] = {
    "business_type": "sdn_bhd",
    "sector": "retail",
    "registered_months": 18,
    "annual_revenue_myr": 250000,
    "is_bumiputera": True,
}


def make_state(**overrides: Any) -> GrantDraftState:
    base: GrantDraftState = {
        "session_id": "sess-1",
        "user_id": "user-1",
        "language": "en",
        "programme_name": "SME Digitalization Grant (SDMG)",
        "business_profile": BUSINESS_PROFILE,
        "export_format": "pdf",
        "tool_calls": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


# The Supabase client reaches nodes through the run config, never through
# graph state — a live client is not checkpoint-serialisable, and putting it
# in state made every /start 500 (see app/agents/runtime.py).
def _config(supabase):
    return {"configurable": {"thread_id": "t-test", "supabase": supabase}}


# ── fetch_grant_node ─────────────────────────────────────────────────────────


class TestFetchGrantNode:

    @pytest.mark.asyncio
    async def test_found_programme(self):
        state = make_state()
        mock_supabase = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[SAMPLE_GRANT]))
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute = mock_execute

        result = await fetch_grant_node(state, _config(mock_supabase))

        assert result["grant_record"] == SAMPLE_GRANT
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_not_found_programme_sets_error_no_crash(self):
        state = make_state(programme_name="Nonexistent Grant")
        mock_supabase = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[]))
        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute = mock_execute

        result = await fetch_grant_node(state, _config(mock_supabase))

        assert result["grant_record"] is None
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_supabase_none_degrades_gracefully(self):
        state = make_state()

        result = await fetch_grant_node(state, _config(None))

        assert result["grant_record"] is None
        assert result["error"]

    @pytest.mark.asyncio
    async def test_missing_programme_name_short_circuits(self):
        state = make_state(programme_name="")
        result = await fetch_grant_node(state)
        assert result["error"]
        assert result["grant_record"] is None


# ── draft_node ───────────────────────────────────────────────────────────────


class TestDraftNode:

    @pytest.mark.asyncio
    async def test_produces_all_four_sections(self):
        state = make_state(grant_record=SAMPLE_GRANT)
        with patch(
            "app.agents.grant_draft_generator.nodes.llm_complete",
            new=AsyncMock(return_value="Generated narrative text."),
        ):
            result = await draft_node(state)

        assert result["executive_summary"]
        assert result["use_of_funds_narrative"]
        assert result["financial_projection_skeleton"]
        assert result["document_checklist"]
        # Checklist minimums from the brief.
        items = {d["item"] for d in result["document_checklist"]}
        assert any("SSM" in i for i in items)
        assert any("LHDN" in i for i in items)
        assert any("Accounts" in i for i in items)
        assert any("Business Plan" in i for i in items)

    @pytest.mark.asyncio
    async def test_financial_skeleton_is_labeled_template_not_real_data(self):
        """Real correctness property: the skeleton must never read as verified
        financial data. Assert on the disclaimer text and the absence of
        fabricated concrete figures."""
        state = make_state(grant_record=SAMPLE_GRANT)
        with patch(
            "app.agents.grant_draft_generator.nodes.llm_complete",
            new=AsyncMock(return_value="Generated narrative text."),
        ):
            result = await draft_node(state)

        skeleton = result["financial_projection_skeleton"]
        assert skeleton["is_template"] is True
        assert "template" in skeleton["disclaimer"].lower() or "not real" in skeleton["disclaimer"].lower()
        for row in skeleton["revenue_projection"]:
            assert row["projected_revenue_myr"] is None
        for row in skeleton["cost_breakdown"]:
            assert row["amount_myr"] is None

    @pytest.mark.asyncio
    async def test_error_state_short_circuits(self):
        state = make_state(error="Grant programme not found: X")
        result = await draft_node(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_placeholder_text(self):
        state = make_state(grant_record=SAMPLE_GRANT)
        with patch(
            "app.agents.grant_draft_generator.nodes.llm_complete",
            new=AsyncMock(return_value=""),
        ):
            result = await draft_node(state)
        assert result["executive_summary"]
        assert result["use_of_funds_narrative"]


# ── compile_node ─────────────────────────────────────────────────────────────


class TestCompileNode:

    @pytest.mark.asyncio
    async def test_compile_sets_awaiting_hitl_and_disclaimer(self):
        state = make_state(
            grant_record=SAMPLE_GRANT,
            executive_summary="Summary text.",
            use_of_funds_narrative="Use of funds text.",
            financial_projection_skeleton={
                "is_template": True,
                "disclaimer": "TEMPLATE ONLY",
                "revenue_projection": [],
                "cost_breakdown": [],
                "funding_allocation": [],
            },
            document_checklist=[{"item": "SSM Registration Certificate", "description": "d", "required": True}],
        )
        result = await compile_node(state)

        assert result["awaiting_hitl"] is True
        assert "verify" in result["report_json"]["disclaimer"].lower()
        assert "SSM Registration Certificate" in result["report_html"]

    @pytest.mark.asyncio
    async def test_compile_with_error_does_not_set_hitl(self):
        state = make_state(error="Grant programme not found: X")
        result = await compile_node(state)
        assert result["awaiting_hitl"] is False
        assert "error" in result["report_json"]


# ── export ───────────────────────────────────────────────────────────────────


class TestGenerateExportNode:

    @pytest.mark.asyncio
    async def test_pdf_export_path(self):
        state = make_state(report_html="<html><body>x</body></html>")
        with patch(
            "app.agents.tools.generate_pdf",
            new=AsyncMock(return_value=("path.pdf", "https://signed.example/path.pdf", "2026-07-29T00:00:00Z")),
        ):
            result = await generate_export_node(state)
        assert result["pdf_storage_path"] == "path.pdf"
        assert result["signed_url"] == "https://signed.example/path.pdf"
        assert result["awaiting_hitl"] is False

    @pytest.mark.asyncio
    async def test_docx_export_path(self):
        state = make_state(export_format="docx", report_json={"programme_name": "X"})
        with patch(
            "app.agents.tools.generate_docx",
            new=AsyncMock(return_value=("path.docx", "https://signed.example/path.docx", "2026-07-29T00:00:00Z")),
        ):
            result = await generate_export_node(state)
        assert result["docx_storage_path"] == "path.docx"
        assert result["signed_url"] == "https://signed.example/path.docx"

    @pytest.mark.asyncio
    async def test_error_state_skips_export(self):
        state = make_state(error="not found")
        result = await generate_export_node(state)
        assert result == {"awaiting_hitl": False}


class TestGenerateDocx:

    @pytest.mark.asyncio
    async def test_produces_valid_docx_with_section_headings(self):
        report_json = {
            "programme_name": "SME Digitalization Grant (SDMG)",
            "executive_summary": "This is the summary.",
            "use_of_funds_narrative": "This is the use of funds.",
            "financial_projection_skeleton": {
                "disclaimer": "TEMPLATE ONLY — not real financial data.",
                "revenue_projection": [{"period": "Year 1", "notes": "fill in"}],
                "cost_breakdown": [{"category": "Manpower"}],
                "funding_allocation": [{"use_of_funds": "Equipment"}],
            },
            "document_checklist": [
                {"item": "SSM Registration Certificate", "description": "cert", "required": True},
            ],
            "disclaimer": "Verify before submission.",
        }
        path, url, expires = await generate_docx(report_json, user_id="user-1", supabase_client=None)

        assert path.endswith(".docx")
        assert url == ""  # no supabase_client -> no upload, matches generate_pdf's degrade shape

    @pytest.mark.asyncio
    async def test_docx_bytes_round_trip_contain_headings(self):
        from docx import Document

        report_json = {
            "programme_name": "Test Grant",
            "executive_summary": "Summary body.",
            "use_of_funds_narrative": "Use of funds body.",
            "financial_projection_skeleton": {
                "disclaimer": "TEMPLATE ONLY",
                "revenue_projection": [],
                "cost_breakdown": [],
                "funding_allocation": [],
            },
            "document_checklist": [],
            "disclaimer": "Verify before submission.",
        }

        mock_supabase = MagicMock()
        mock_supabase.storage.from_.return_value.upload = MagicMock()
        mock_supabase.storage.from_.return_value.create_signed_url = MagicMock(
            return_value={"signedURL": "https://signed.example/f.docx"}
        )

        captured: dict[str, bytes] = {}

        def fake_upload(path, data, opts):
            captured["bytes"] = data

        mock_supabase.storage.from_.return_value.upload = fake_upload

        await generate_docx(report_json, user_id="user-1", supabase_client=mock_supabase)

        doc = Document(io.BytesIO(captured["bytes"]))
        headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
        assert any("Executive Summary" in h for h in headings)
        assert any("Financial Projection Skeleton" in h for h in headings)
        assert any("Required Document Checklist" in h for h in headings)


# ── credit exemption / timing ────────────────────────────────────────────────


class TestCreditExemption:

    def test_is_credit_exempt_covers_both_agents(self):
        from services.agent_registry import is_credit_exempt

        assert is_credit_exempt("business", "compliance-drafter") is True
        assert is_credit_exempt("business", "grant-draft-generator") is True
        assert is_credit_exempt("free", "grant-draft-generator") is False
        assert is_credit_exempt("pro", "grant-draft-generator") is False
        assert is_credit_exempt("free", "grant-draft-generator", role="primary_admin") is True

    def test_registry_has_grant_draft_generator_priced_at_3_credits(self):
        from services.agent_registry import load_agent_registry

        reg = load_agent_registry(None)
        assert "grant-draft-generator" in reg
        assert reg["grant-draft-generator"].credit_cost == 3
        assert reg["grant-draft-generator"].plan_required == "free"


class TestConfirmDispatchBilling:
    """Credits must be deducted at /confirm, never at /start — matches
    compliance-drafter's HITL billing-on-generation pattern."""

    def test_confirm_handler_registered_for_grant_draft_generator(self):
        from app.services.agent_runner import AGENT_CONFIRM_HANDLERS, confirm_grant_draft_generator

        assert AGENT_CONFIRM_HANDLERS["grant-draft-generator"] is confirm_grant_draft_generator

    def test_start_handler_does_not_deduct_credits(self):
        """start_grant_draft_generator never calls deduct_credits; billing is
        wired at the router's /confirm endpoint only (agents.py), same as
        compliance-drafter."""
        import inspect

        from app.services.agent_runner import start_grant_draft_generator

        src = inspect.getsource(start_grant_draft_generator)
        assert "deduct_credits" not in src
