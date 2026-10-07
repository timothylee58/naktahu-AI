"""tests/test_grant_compatibility.py

Unit + endpoint tests for the grant stacking compatibility checker.

Supabase is mocked following the convention in tests/test_eligibility_agent.py:
a MagicMock whose terminal .execute() is an AsyncMock (the repo's Supabase
client is awaited, see grant_rag_node).
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.eligibility_agent.analyst_node import _build_stacking_matrix
from app.agents.eligibility_agent.compatibility import (
    canonical_name,
    grant_compatibility_check,
)
from app.routers import eligibility as eligibility_router

MDAG = "Malaysia Digital Acceleration Grant (MDAG)"
SDMG = "SME Digitalization Grant (SDMG)"
MADANI = "MSME Digital Grant MADANI"
HRD = "HRD Corp Training Fund"


RULE_ROWS: list[dict[str, Any]] = [
    {
        "id": "r1",
        "programme_a": "CIP Spark",
        "programme_b": "CIP Sprint",
        "rule_type": "conflict",
        "overlap_scope": None,
        "explanation_en": "Stage-gated: one stage at a time.",
        "explanation_bm": "Berperingkat: satu peringkat sahaja.",
        "source_url": "https://cradle.com.my/programmes",
        "last_verified": "2026-07-01",
    },
    {
        "id": "r2",
        "programme_a": MDAG,
        "programme_b": SDMG,
        "rule_type": "partial_overlap",
        "overlap_scope": "same_project_cost",
        "explanation_en": "Cannot claim the same project cost under both.",
        "explanation_bm": "Tidak boleh menuntut kos projek yang sama.",
        "source_url": "https://www.mdec.my/malaysia-digital/mdag",
        "last_verified": "2026-07-01",
    },
    {
        "id": "r3",
        "programme_a": SDMG,
        "programme_b": HRD,
        "rule_type": "stackable",
        "overlap_scope": None,
        "explanation_en": "Tool vs training — separate claim streams.",
        "explanation_bm": "Alat berbanding latihan — aliran tuntutan berasingan.",
        "source_url": "https://www.hrdcorp.gov.my",
        "last_verified": "2026-07-01",
    },
]

GRANT_ROWS: list[dict[str, Any]] = [
    {
        "programme_name": "CIP Spark",
        "agency": "Cradle Fund",
        "stackable_with": ["SME Digitalization Grant"],
        "conflicts_with": ["CIP Sprint"],
        "application_url": "https://cradle.com.my/programmes/cip-spark",
        "source_url": "https://cradle.com.my/programmes",
    },
    {
        "programme_name": "CIP Sprint",
        "agency": "Cradle Fund",
        "stackable_with": [],
        "conflicts_with": ["CIP Spark"],
        "application_url": "",
        "source_url": "https://cradle.com.my/programmes",
    },
    {
        "programme_name": MDAG,
        "agency": "MDEC",
        "stackable_with": ["CIP Spark"],
        "conflicts_with": [],
        "application_url": "",
        "source_url": "https://www.mdec.my",
    },
    {
        "programme_name": SDMG,
        "agency": "SME Corp / BSN",
        "stackable_with": ["HRD Corp Training Fund"],
        "conflicts_with": [],
        "application_url": "",
        "source_url": "https://www.smecorp.gov.my",
    },
    {
        "programme_name": HRD,
        "agency": "HRD Corp",
        "stackable_with": ["SME Digitalization Grant"],
        "conflicts_with": [],
        "application_url": "",
        "source_url": "https://www.hrdcorp.gov.my",
    },
]


def _mock_supabase(*, rules: list[dict[str, Any]] | None, grants: list[dict[str, Any]]) -> MagicMock:
    """Mock Supabase client. `rules=None` simulates migration 021 not applied
    (the rules-table query raises)."""
    sb = MagicMock()

    def _table(name: str) -> MagicMock:
        chain = MagicMock()
        if name == "grant_compatibility_rules":
            if rules is None:
                chain.select.return_value.in_.return_value.execute = AsyncMock(
                    side_effect=Exception('relation "grant_compatibility_rules" does not exist')
                )
            else:
                chain.select.return_value.in_.return_value.execute = AsyncMock(
                    return_value=MagicMock(data=list(rules))
                )
        else:
            chain.select.return_value.in_.return_value.execute = AsyncMock(
                return_value=MagicMock(data=list(grants))
            )
        return chain

    sb.table.side_effect = _table
    return sb


# ═══════════════════════════════════════════════════════════════════════════
# CHECKER — three verdicts
# ═══════════════════════════════════════════════════════════════════════════
class TestCompatibilityChecker:

    @pytest.mark.asyncio
    async def test_all_three_verdicts(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        result = await grant_compatibility_check(
            ["CIP Spark", "CIP Sprint", MDAG, SDMG, HRD], sb
        )
        verdicts = {
            (p["programme_a"], p["programme_b"]): p["verdict"] for p in result["pairs"]
        }
        assert verdicts[("CIP Spark", "CIP Sprint")] == "conflict"
        assert verdicts[(MDAG, SDMG)] == "partial_overlap"
        assert verdicts[(HRD, SDMG)] == "stackable"
        assert result["has_conflicts"] is True
        assert result["conflict_count"] == 1
        assert result["partial_overlap_count"] == 1
        assert result["degraded"] is False

    @pytest.mark.asyncio
    async def test_partial_overlap_carries_scope_and_explanation(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        result = await grant_compatibility_check([MDAG, SDMG], sb)
        pair = result["pairs"][0]
        assert pair["overlap_scope"] == "same_project_cost"
        assert "same project cost" in pair["explanation"]
        assert pair["source"] == "rules_table"

    @pytest.mark.asyncio
    async def test_bm_explanation_selected(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        result = await grant_compatibility_check([MDAG, SDMG], sb, language="bm")
        assert result["language"] == "bm"
        assert "kos projek" in result["pairs"][0]["explanation"]

    @pytest.mark.asyncio
    async def test_unknown_pair_is_not_stackable(self):
        # MDAG vs HRD: no rule row, and neither legacy array names the other.
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        result = await grant_compatibility_check([MDAG, HRD], sb)
        pair = result["pairs"][0]
        assert pair["verdict"] == "unknown"
        assert pair["verdict"] != "stackable"
        assert pair["source"] == "none"
        assert result["unknown_count"] == 1
        assert result["stackable_count"] == 0

    @pytest.mark.asyncio
    async def test_unrecognised_programme_reported(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        result = await grant_compatibility_check(["CIP Spark", "Totally Fake Grant"], sb)
        assert result["unrecognised_programmes"] == ["Totally Fake Grant"]
        assert result["pairs"][0]["verdict"] == "unknown"

    @pytest.mark.asyncio
    async def test_alias_canonicalised(self):
        assert canonical_name("MDEC MDAG") == MDAG
        assert canonical_name("  SME Digitalization Grant ") == SDMG
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        result = await grant_compatibility_check(["MDEC MDAG", "SDMG"], sb)
        assert result["programmes"] == [MDAG, SDMG]
        assert result["pairs"][0]["verdict"] == "partial_overlap"

    @pytest.mark.asyncio
    async def test_duplicate_names_deduplicated(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        result = await grant_compatibility_check(["CIP Spark", "CIP Spark", "CIP Sprint"], sb)
        assert result["programmes"] == ["CIP Spark", "CIP Sprint"]
        assert len(result["pairs"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# DEGRADED MODE (Trap #4 / Trap #5)
# ═══════════════════════════════════════════════════════════════════════════
class TestDegradedMode:

    @pytest.mark.asyncio
    async def test_supabase_none_does_not_crash(self):
        result = await grant_compatibility_check(["CIP Spark", "CIP Sprint"], None)
        assert result["degraded"] is True
        assert result["pairs"][0]["verdict"] == "unknown"
        assert result["unrecognised_programmes"] == []
        assert result["advice"]

    @pytest.mark.asyncio
    async def test_rules_table_missing_falls_back_to_arrays(self):
        sb = _mock_supabase(rules=None, grants=GRANT_ROWS)
        result = await grant_compatibility_check(["CIP Spark", "CIP Sprint", SDMG], sb)
        assert result["degraded"] is True
        verdicts = {
            (p["programme_a"], p["programme_b"]): (p["verdict"], p["source"])
            for p in result["pairs"]
        }
        # Legacy conflicts_with array still catches the Cradle conflict...
        assert verdicts[("CIP Spark", "CIP Sprint")] == ("conflict", "legacy_array")
        # ...and the alias 'SME Digitalization Grant' resolves to canonical SDMG.
        assert verdicts[("CIP Spark", SDMG)] == ("stackable", "legacy_array")
        # No partial-overlap detection is possible from binary arrays.
        assert result["partial_overlap_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# _build_stacking_matrix — backward-compat regression guard
# ═══════════════════════════════════════════════════════════════════════════
def _matched(name: str, **kw: Any) -> dict[str, Any]:
    base = {
        "programme_name": name,
        "grant_type": "matching",
        "amount_min_myr": 1000,
        "amount_max_myr": 5000,
        "eligibility_score": 0.9,
        "processing_weeks_min": 4,
        "stackable_with": [],
        "conflicts_with": [],
    }
    base.update(kw)
    return base


class TestStackingMatrixUpgrade:

    def test_original_keys_preserved_without_rules(self):
        a = _matched("CIP Spark", grant_type="non_dilutive", conflicts_with=["CIP Sprint"])
        b = _matched("CIP Sprint", conflicts_with=["CIP Spark"])
        matrix = _build_stacking_matrix([a, b])
        for key in (
            "conflict_pairs",
            "stackable_pairs",
            "recommended_sequence",
            "total_potential_myr_min",
            "total_potential_myr_max",
        ):
            assert key in matrix
        assert matrix["conflict_pairs"] == [["CIP Spark", "CIP Sprint"]]
        # Naive totals keep their original sum-of-everything meaning.
        assert matrix["total_potential_myr_min"] == 2000
        assert matrix["total_potential_myr_max"] == 10000
        assert set(matrix["recommended_sequence"]) == {"CIP Spark", "CIP Sprint"}
        # New key present and empty when no rules are supplied.
        assert matrix["partial_overlap_pairs"] == []

    def test_realistic_total_excludes_conflicting_grant(self):
        a = _matched("CIP Spark", grant_type="non_dilutive", conflicts_with=["CIP Sprint"])
        b = _matched("CIP Sprint", conflicts_with=["CIP Spark"])
        matrix = _build_stacking_matrix([a, b])
        assert matrix["total_potential_myr_max"] == 10000
        assert matrix["realistic_total_myr_max"] == 5000
        assert matrix["excluded_from_realistic_total"] == ["CIP Sprint"]

    def test_partial_overlap_pairs_from_rules(self):
        a = _matched(MDAG)
        b = _matched(SDMG)
        rules = {(MDAG, SDMG): RULE_ROWS[1]}
        matrix = _build_stacking_matrix([a, b], rules)
        assert len(matrix["partial_overlap_pairs"]) == 1
        entry = matrix["partial_overlap_pairs"][0]
        assert entry["pair"] == [MDAG, SDMG]
        assert entry["overlap_scope"] == "same_project_cost"
        # Both can be held, so neither is excluded from the realistic total.
        assert matrix["realistic_total_myr_max"] == 10000

    def test_rules_table_conflict_overrides_legacy_stackable(self):
        a = _matched("CIP Spark", stackable_with=["CIP Sprint"])
        b = _matched("CIP Sprint", stackable_with=["CIP Spark"])
        rules = {("CIP Spark", "CIP Sprint"): RULE_ROWS[0]}
        matrix = _build_stacking_matrix([a, b], rules)
        assert matrix["conflict_pairs"] == [["CIP Spark", "CIP Sprint"]]
        assert matrix["stackable_pairs"] == []


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════
def _client(supabase: Any) -> TestClient:
    app = FastAPI()
    app.include_router(eligibility_router.router)
    app.state.supabase = supabase
    return TestClient(app)


class TestCompatibilityEndpoint:

    def test_happy_path_200(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        res = _client(sb).post(
            "/api/v1/eligibility/compatibility",
            json={"programme_names": ["CIP Spark", "CIP Sprint"], "language": "en"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["has_conflicts"] is True
        assert body["pairs"][0]["verdict"] == "conflict"
        assert body["degraded"] is False

    def test_language_ms_alias_normalised(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        res = _client(sb).post(
            "/api/v1/eligibility/compatibility",
            json={"programme_names": [MDAG, SDMG], "language": "ms"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["language"] == "bm"

    def test_too_few_programmes_422(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        res = _client(sb).post(
            "/api/v1/eligibility/compatibility",
            json={"programme_names": ["CIP Spark"]},
        )
        assert res.status_code == 422

    def test_too_many_programmes_422(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        res = _client(sb).post(
            "/api/v1/eligibility/compatibility",
            json={"programme_names": [f"Grant {i}" for i in range(11)]},
        )
        assert res.status_code == 422

    def test_oversized_name_422(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        res = _client(sb).post(
            "/api/v1/eligibility/compatibility",
            json={"programme_names": ["CIP Spark", "x" * 201]},
        )
        assert res.status_code == 422

    def test_bad_language_422(self):
        sb = _mock_supabase(rules=RULE_ROWS, grants=GRANT_ROWS)
        res = _client(sb).post(
            "/api/v1/eligibility/compatibility",
            json={"programme_names": ["CIP Spark", "CIP Sprint"], "language": "fr"},
        )
        assert res.status_code == 422

    def test_supabase_none_503(self):
        res = _client(None).post(
            "/api/v1/eligibility/compatibility",
            json={"programme_names": ["CIP Spark", "CIP Sprint"]},
        )
        assert res.status_code == 503
