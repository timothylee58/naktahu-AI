"""Tests for the Research Synthesiser scale-up: full-domain keyword
detection and the new synthesis_node (ILMU primary, Anthropic fallback).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.research_synthesiser.graph import (
    _build_synthesis_prompt,
    _detect_domains,
    _merge_findings,
    merge_node,
    synthesis_node,
)


class TestDetectDomains:
    def test_finds_tax_domain(self):
        assert "tax" in _detect_domains("How do I pay cukai pendapatan?")

    def test_finds_healthcare_previously_undetected(self):
        # The original version had no healthcare keyword at all — it would
        # have silently fallen through to government+finance+legal for a
        # clinic question, which is exactly the gap this fixes.
        assert "healthcare" in _detect_domains("Where is the nearest klinik kesihatan?")

    def test_finds_parliament_previously_undetected(self):
        assert "parliament" in _detect_domains("Who is my ahli parlimen for this constituency?")

    def test_finds_welfare_previously_undetected(self):
        assert "welfare" in _detect_domains("What bantuan rahmah am I eligible for?")

    def test_no_keyword_match_falls_back_to_broad_triple(self):
        assert _detect_domains("asdkfjaslkdjf") == ["government", "finance", "legal"]

    def test_caps_at_three_domains(self):
        # A query hitting many keyword sets at once must still respect
        # _MAX_DOMAINS — same fan-out-cost reasoning the original had.
        query = "cukai pendidikan kesihatan parlimen tanah bantuan kewangan"
        assert len(_detect_domains(query)) <= 3


class TestMergeFindings:
    def _state(self):
        return {
            "domain_results": [
                {
                    "domain": "tax",
                    "findings": [
                        {
                            "domain": "tax",
                            "source_title": "LHDN e-Filing Guide",
                            "source_url": "https://lhdn.gov.my/efiling",
                            "summary": "e-Filing opens 1 March each year.",
                            "similarity": 0.82,
                        },
                    ],
                },
                {
                    "domain": "finance",
                    "findings": [
                        {
                            "domain": "finance",
                            "source_title": "LHDN e-Filing Guide",  # duplicate URL
                            "source_url": "https://lhdn.gov.my/efiling",
                            "summary": "duplicate",
                            "similarity": 0.5,
                        },
                        {
                            "domain": "finance",
                            "source_title": "BNM Consumer Guide",
                            "source_url": "https://bnm.gov.my/consumer",
                            "summary": "Banks must disclose fees upfront.",
                            "similarity": 0.6,
                        },
                    ],
                },
            ],
        }

    def test_deduplicates_by_url(self):
        citations, findings = _merge_findings(self._state())
        assert len(citations) == 2
        assert len(findings) == 2

    def test_citations_never_carry_the_excerpt_text(self):
        citations, _ = _merge_findings(self._state())
        assert all("excerpt" not in c and "summary" not in c for c in citations)

    def test_findings_carry_excerpt_for_synthesis(self):
        _, findings = _merge_findings(self._state())
        assert any("e-Filing opens" in f["excerpt"] for f in findings)

    @pytest.mark.asyncio
    async def test_merge_node_keeps_excerpts_out_of_public_fields(self):
        result = await merge_node(self._state())
        assert "_findings_with_excerpts" in result
        assert result["merged_citations"] == result["citations"]
        assert len(result["_findings_with_excerpts"]) == len(result["merged_citations"])


class TestBuildSynthesisPrompt:
    def test_skips_findings_with_empty_excerpt(self):
        findings = [
            {"domain": "tax", "title": "A", "excerpt": ""},
            {"domain": "tax", "title": "B", "excerpt": "Real content here."},
        ]
        prompt = _build_synthesis_prompt("test query", findings)
        assert "Real content here." in prompt
        assert prompt.count("- [") == 1

    def test_includes_the_query(self):
        prompt = _build_synthesis_prompt("How do I register a company?", [])
        assert "How do I register a company?" in prompt


class TestSynthesisNode:
    @pytest.mark.asyncio
    async def test_no_findings_skips_llm_call_entirely(self):
        # Grounding-free synthesis would just invite fabrication — must not
        # even attempt an LLM call when there's nothing to synthesise from.
        with patch("app.agents.research_synthesiser.graph.ilmu_client") as mock_ilmu:
            result = await synthesis_node({"query": "x", "language": "en", "_findings_with_excerpts": []})
        assert result == {"summary": ""}
        mock_ilmu.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_ilmu_success_returns_its_text(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="Synthesised answer."))]
        state = {
            "query": "How do I register a company?",
            "language": "en",
            "_findings_with_excerpts": [{"domain": "business", "title": "SSM Guide", "excerpt": "Register online via SSM."}],
        }
        with patch(
            "app.agents.research_synthesiser.graph.ilmu_client.chat.completions.create",
            new=AsyncMock(return_value=mock_resp),
        ):
            result = await synthesis_node(state)
        assert result == {"summary": "Synthesised answer."}

    @pytest.mark.asyncio
    async def test_ilmu_failure_falls_back_to_anthropic(self):
        state = {
            "query": "q",
            "language": "en",
            "_findings_with_excerpts": [{"domain": "tax", "title": "T", "excerpt": "e"}],
        }
        anthropic_block = MagicMock(type="text", text="Fallback answer.")
        anthropic_resp = MagicMock(content=[anthropic_block])
        with patch(
            "app.agents.research_synthesiser.graph.ilmu_client.chat.completions.create",
            new=AsyncMock(side_effect=RuntimeError("ilmu down")),
        ), patch(
            "app.agents.research_synthesiser.graph.anthropic_client.messages.create",
            new=AsyncMock(return_value=anthropic_resp),
        ):
            result = await synthesis_node(state)
        assert result == {"summary": "Fallback answer."}

    @pytest.mark.asyncio
    async def test_both_providers_failing_degrades_to_empty_summary_not_raise(self):
        state = {
            "query": "q",
            "language": "en",
            "_findings_with_excerpts": [{"domain": "tax", "title": "T", "excerpt": "e"}],
        }
        with patch(
            "app.agents.research_synthesiser.graph.ilmu_client.chat.completions.create",
            new=AsyncMock(side_effect=RuntimeError("ilmu down")),
        ), patch(
            "app.agents.research_synthesiser.graph.anthropic_client.messages.create",
            new=AsyncMock(side_effect=RuntimeError("anthropic down too")),
        ):
            result = await synthesis_node(state)  # must not raise
        assert result == {"summary": ""}

    @pytest.mark.asyncio
    async def test_language_instruction_selected_by_state_language(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="Jawapan."))]
        state = {
            "query": "q",
            "language": "bm",
            "_findings_with_excerpts": [{"domain": "tax", "title": "T", "excerpt": "e"}],
        }
        create_mock = AsyncMock(return_value=mock_resp)
        with patch("app.agents.research_synthesiser.graph.ilmu_client.chat.completions.create", new=create_mock):
            await synthesis_node(state)
        sent_messages = create_mock.call_args.kwargs["messages"]
        system_message = next(m["content"] for m in sent_messages if m["role"] == "system")
        assert "Bahasa Malaysia" in system_message
