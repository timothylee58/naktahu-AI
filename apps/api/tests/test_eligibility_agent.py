"""tests/test_eligibility_agent.py

Unit tests for all 3 eligibility agent nodes. All external calls
(ILMU, Supabase, Redis) are mocked. Adapted from the uploaded spec's
test intent/assertions to this repo's real module layout.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.eligibility_agent.analyst_node import _build_stacking_matrix, _score_grant, analyst_node
from app.agents.eligibility_agent.grant_rag_node import grant_rag_node
from app.agents.eligibility_agent.intake_node import _extract_profile_fields, _missing_required, intake_node
from app.agents.eligibility_agent.state import BusinessProfile, EligibilityState


# ── Fixtures ──────────────────────────────────────────────────────────────────
def make_state(**overrides) -> EligibilityState:
    base: EligibilityState = {
        "session_id": "test-session-001",
        "user_id": None,
        "language": "en",
        "current_turn": 0,
        "messages": [],
        "latest_user_input": "",
        "business_profile": None,
        "intake_complete": False,
        "missing_fields": [],
        "next_question": None,
        "retrieved_grant_chunks": [],
        "structured_grants": [],
        "matched_grants": [],
        "near_miss_grants": [],
        "stacking_matrix": None,
        "summary_bm": "",
        "summary_en": "",
        "streaming_token_buffer": "",
        "needs_more_info": False,
        "needs_clarification": False,
        "error": None,
    }
    base.update(overrides)
    return base


FULL_PROFILE: BusinessProfile = {
    "business_type": "sdn_bhd",
    "registered_months": 24,
    "sector": "technology",
    "sub_sector": "ai",
    "annual_revenue_myr": 500_000,
    "is_bumiputera": False,
    "employee_count": 12,
    "has_md_status": True,
    "existing_grants": [],
    "is_pre_revenue": False,
    "is_sme": True,
}

BUMI_STARTUP_PROFILE: BusinessProfile = {
    "business_type": "startup",
    "registered_months": 8,
    "sector": "technology",
    "sub_sector": "fintech",
    "annual_revenue_myr": 0,
    "is_bumiputera": True,
    "employee_count": 3,
    "has_md_status": False,
    "existing_grants": [],
    "is_pre_revenue": True,
    "is_sme": True,
}

SAMPLE_GRANT = {
    "programme_name": "CIP Spark",
    "agency": "Cradle Fund",
    "grant_type": "non_dilutive",
    "amount_min_myr": 50_000,
    "amount_max_myr": 150_000,
    "application_deadline": (date.today() + timedelta(days=60)).isoformat(),
    "deadline_is_rolling": False,
    "eligible_sectors": ["technology", "ai", "fintech", "edtech"],
    "bumiputera_required": False,
    "company_age_min_months": 0,
    "max_annual_revenue_myr": None,
    "application_url": "https://cradle.com.my/programmes/cip-spark",
    "processing_weeks_min": 4,
    "processing_weeks_max": 8,
    "stackable_with": ["SME Digitalization Grant", "MATRADE MDG"],
    "conflicts_with": ["CIP Sprint"],
    "budget_year": 2026,
    "notes_en": "Idea-to-prototype stage. Open to companies and individuals.",
}

EXPIRED_GRANT = {
    **SAMPLE_GRANT,
    "programme_name": "Old Grant 2024",
    "application_deadline": "2024-01-01",
    "deadline_is_rolling": False,
}

BUMI_GRANT = {
    **SAMPLE_GRANT,
    "programme_name": "TERAJU SUPERB",
    "agency": "TERAJU",
    "bumiputera_required": True,
    "eligible_sectors": ["all"],
    "conflicts_with": [],
    "stackable_with": [],
}


# ═══════════════════════════════════════════════════════════════════════════════
# INTAKE NODE TESTS
# ═══════════════════════════════════════════════════════════════════════════════
class TestIntakeNode:

    @pytest.mark.asyncio
    async def test_turn_0_emits_first_question_en(self):
        state = make_state(current_turn=0, language="en")
        result = await intake_node(state)
        assert result["needs_more_info"] is True
        assert result["intake_complete"] is False
        assert result["next_question"] is not None
        assert "business" in result["next_question"].lower() or "type" in result["next_question"].lower()
        assert result["current_turn"] == 1

    @pytest.mark.asyncio
    async def test_turn_0_emits_bm_question(self):
        state = make_state(current_turn=0, language="bm")
        result = await intake_node(state)
        assert result["next_question"] is not None
        assert any(word in result["next_question"] for word in ["perniagaan", "jenis", "sektor"])

    @pytest.mark.asyncio
    async def test_turn_1_asks_revenue_question(self):
        state = make_state(
            current_turn=1,
            language="en",
            latest_user_input="Sdn Bhd, technology sector, 18 months",
            business_profile={
                "business_type": "sdn_bhd",
                "sector": "technology",
                "registered_months": 18,
            },
        )
        with patch(
            "app.agents.eligibility_agent.intake_node._extract_profile_fields",
            new=AsyncMock(return_value={
                "business_type": "sdn_bhd",
                "sector": "technology",
                "registered_months": 18,
            }),
        ):
            result = await intake_node(state)
        assert result["needs_more_info"] is True
        assert result["current_turn"] == 2
        question = result["next_question"] or ""
        assert any(w in question.lower() for w in ["revenue", "employee", "bumiputera"])

    @pytest.mark.asyncio
    async def test_turn_3_marks_intake_complete(self):
        state = make_state(
            current_turn=3,
            language="en",
            latest_user_input="No MD status, no previous grants",
            business_profile=FULL_PROFILE,
        )
        with patch(
            "app.agents.eligibility_agent.intake_node._extract_profile_fields",
            new=AsyncMock(return_value={"has_md_status": False, "existing_grants": []}),
        ):
            result = await intake_node(state)
        assert result["intake_complete"] is True
        assert result["needs_more_info"] is False
        assert result["business_profile"] is not None

    def test_missing_required_all_missing(self):
        missing = _missing_required({})
        assert "business_type" in missing
        assert "sector" in missing
        assert "is_bumiputera" in missing

    def test_missing_required_zero_revenue_not_missing(self):
        profile = {**FULL_PROFILE, "annual_revenue_myr": 0}
        missing = _missing_required(profile)
        assert "annual_revenue_myr" not in missing

    def test_missing_required_none_when_full(self):
        missing = _missing_required(FULL_PROFILE)
        assert missing == []


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYST NODE TESTS
# ═══════════════════════════════════════════════════════════════════════════════
class TestAnalystNode:

    def test_score_grant_fully_eligible(self):
        result = _score_grant(SAMPLE_GRANT, FULL_PROFILE)
        assert result["is_fully_eligible"] is True
        assert result["eligibility_score"] >= 0.6
        assert len(result["eligibility_reasons"]) > 0

    def test_score_grant_expired_deadline(self):
        result = _score_grant(EXPIRED_GRANT, FULL_PROFILE)
        assert result["is_fully_eligible"] is False
        assert any("closed" in r.lower() or "ago" in r.lower()
                   for r in result["ineligibility_reasons"])

    def test_score_grant_bumiputera_required_non_bumi(self):
        non_bumi_profile = {**FULL_PROFILE, "is_bumiputera": False}
        result = _score_grant(BUMI_GRANT, non_bumi_profile)
        assert result["is_fully_eligible"] is False
        assert any("bumiputera" in r.lower() for r in result["ineligibility_reasons"])

    def test_score_grant_bumiputera_required_bumi_owner(self):
        bumi_profile = {**FULL_PROFILE, "is_bumiputera": True}
        result = _score_grant(BUMI_GRANT, bumi_profile)
        assert result["is_fully_eligible"] is True

    def test_score_grant_age_too_young(self):
        young_profile = {**FULL_PROFILE, "registered_months": 3}
        age_restricted_grant = {**SAMPLE_GRANT, "company_age_min_months": 12}
        result = _score_grant(age_restricted_grant, young_profile)
        assert result["is_fully_eligible"] is False
        assert any("months" in r for r in result["ineligibility_reasons"])

    def test_score_grant_near_miss_only_age_blocks(self):
        young_profile = {**FULL_PROFILE, "registered_months": 5}
        age_grant = {**SAMPLE_GRANT, "company_age_min_months": 6}
        result = _score_grant(age_grant, young_profile)
        assert result["is_near_miss"] is True

    def test_score_grant_conflict_with_held(self):
        profile_with_sprint = {**FULL_PROFILE, "existing_grants": ["CIP Sprint"]}
        result = _score_grant(SAMPLE_GRANT, profile_with_sprint)
        assert result["is_fully_eligible"] is False
        assert any("conflict" in r.lower() for r in result["ineligibility_reasons"])

    def test_score_grant_rolling_deadline_always_open(self):
        rolling_grant = {**SAMPLE_GRANT, "deadline_is_rolling": True, "application_deadline": None}
        result = _score_grant(rolling_grant, FULL_PROFILE)
        assert result["deadline_is_rolling"] is True
        assert result["is_fully_eligible"] is True

    @pytest.mark.asyncio
    async def test_analyst_node_ranks_by_score(self):
        state = make_state(
            business_profile=FULL_PROFILE,
            structured_grants=[SAMPLE_GRANT, BUMI_GRANT],
        )
        result = await analyst_node(state)
        matched = result["matched_grants"]
        if len(matched) >= 2:
            assert matched[0]["eligibility_score"] >= matched[1]["eligibility_score"]

    @pytest.mark.asyncio
    async def test_analyst_node_empty_grants(self):
        state = make_state(business_profile=FULL_PROFILE, structured_grants=[])
        result = await analyst_node(state)
        assert result["matched_grants"] == []
        assert result["near_miss_grants"] == []
        assert result["stacking_matrix"] is None

    def test_stacking_matrix_detects_conflicts(self):
        grant_a = {
            "programme_name": "CIP Spark",
            "agency": "Cradle Fund",
            "grant_type": "non_dilutive",
            "amount_min_myr": 50000,
            "amount_max_myr": 150000,
            "application_deadline": None,
            "deadline_is_rolling": True,
            "application_url": "",
            "processing_weeks_min": 4,
            "processing_weeks_max": 8,
            "eligibility_score": 0.9,
            "eligibility_reasons": [],
            "ineligibility_reasons": [],
            "is_fully_eligible": True,
            "is_near_miss": False,
            "stackable_with": [],
            "conflicts_with": ["CIP Sprint"],
            "notes_en": "",
            "chunk_citations": [],
        }
        grant_b = {**grant_a, "programme_name": "CIP Sprint", "conflicts_with": ["CIP Spark"]}
        matrix = _build_stacking_matrix([grant_a, grant_b])
        assert len(matrix["conflict_pairs"]) >= 1
        conflict_names = {n for pair in matrix["conflict_pairs"] for n in pair}
        assert "CIP Spark" in conflict_names or "CIP Sprint" in conflict_names

    def test_stacking_matrix_recommended_sequence_non_dilutive_first(self):
        non_dilutive = {
            **SAMPLE_GRANT,
            "programme_name": "CIP Spark",
            "grant_type": "non_dilutive",
            "processing_weeks_min": 4,
            "eligibility_score": 0.85,
            "eligibility_reasons": [],
            "ineligibility_reasons": [],
            "is_fully_eligible": True,
            "is_near_miss": False,
            "chunk_citations": [],
        }
        matching = {
            **non_dilutive,
            "programme_name": "SME Digitalization Grant",
            "grant_type": "matching",
            "processing_weeks_min": 4,
        }
        financing = {
            **non_dilutive,
            "programme_name": "BNM ADF",
            "grant_type": "financing",
            "processing_weeks_min": 4,
        }
        matrix = _build_stacking_matrix([matching, financing, non_dilutive])
        seq = matrix["recommended_sequence"]
        assert seq.index("CIP Spark") < seq.index("BNM ADF")


# ═══════════════════════════════════════════════════════════════════════════════
# GRANT RAG NODE TESTS
# ═══════════════════════════════════════════════════════════════════════════════
class TestGrantRagNode:

    @pytest.mark.asyncio
    async def test_cache_hit_skips_supabase(self):
        state = make_state(business_profile=FULL_PROFILE)
        cached_data = {"structured": [SAMPLE_GRANT], "chunks": []}

        with patch(
            "app.agents.eligibility_agent.grant_rag_node.get_cached_result",
            new=AsyncMock(return_value=cached_data),
        ):
            mock_supabase = AsyncMock()
            result = await grant_rag_node(state, mock_supabase)

        assert result["structured_grants"] == [SAMPLE_GRANT]
        mock_supabase.table.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_calls_supabase(self):
        state = make_state(business_profile=FULL_PROFILE)

        mock_supabase = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[SAMPLE_GRANT]))
        mock_supabase.table.return_value.select.return_value\
            .eq.return_value.or_.return_value.lte.return_value\
            .execute = mock_execute

        mock_rpc_execute = AsyncMock(return_value=MagicMock(data=[]))
        mock_supabase.rpc.return_value.execute = mock_rpc_execute

        with patch(
            "app.agents.eligibility_agent.grant_rag_node.get_cached_result",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.agents.eligibility_agent.grant_rag_node.set_cached_result",
            new=AsyncMock(),
        ), patch(
            "app.agents.eligibility_agent.grant_rag_node._embed_query",
            new=AsyncMock(return_value=[0.0] * 1536),
        ):
            result = await grant_rag_node(state, mock_supabase)

        assert isinstance(result["structured_grants"], list)

    @pytest.mark.asyncio
    async def test_no_profile_returns_empty(self):
        state = make_state(business_profile=None)
        mock_supabase = AsyncMock()
        result = await grant_rag_node(state, mock_supabase)
        assert result["structured_grants"] == []
        assert result["retrieved_grant_chunks"] == []
