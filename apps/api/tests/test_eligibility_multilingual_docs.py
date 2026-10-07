"""Mandarin support and required-documents plumbing for the Eligibility Agent."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.eligibility_agent import synthesiser_node as syn
from app.agents.eligibility_agent.analyst_node import _normalise_documents, _score_grant
from app.agents.eligibility_agent.compatibility import (
    _advice,
    _fallback_explanation,
    grant_compatibility_check,
)
from app.agents.eligibility_agent.intake_node import _QUESTIONS, intake_node
from app.routers import eligibility as eligibility_router

_CJK = re.compile(r"[一-鿿]")

PROFILE: dict[str, Any] = {
    "business_type": "sdn_bhd",
    "registered_months": 24,
    "sector": "technology",
    "annual_revenue_myr": 500_000,
    "is_bumiputera": False,
    "employee_count": 12,
    "existing_grants": [],
}

GRANT: dict[str, Any] = {
    "programme_name": "CIP Spark",
    "agency": "Cradle Fund",
    "application_deadline": (date.today() + timedelta(days=60)).isoformat(),
    "deadline_is_rolling": False,
    "eligible_sectors": ["technology"],
    "bumiputera_required": False,
    "company_age_min_months": 0,
    "max_annual_revenue_myr": None,
    "application_url": "https://cradle.com.my/programmes/cip-spark",
    "conflicts_with": [],
    "stackable_with": [],
}


# ── Mandarin intake ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("turn", [0, 1, 2])
async def test_zh_intake_asks_every_question_in_chinese(turn):
    out = await intake_node({"current_turn": turn, "language": "zh"})
    assert _CJK.search(out["next_question"])
    assert out["next_question"] == _QUESTIONS["zh"][turn]


async def test_unknown_language_still_falls_back_to_english_and_bm_is_unchanged():
    en = await intake_node({"current_turn": 0, "language": "fr"})
    assert en["next_question"] == _QUESTIONS["en"][0]
    bm = await intake_node({"current_turn": 0, "language": "bm"})
    assert bm["next_question"] == _QUESTIONS["bm"][0]


def test_all_three_languages_ask_the_same_number_of_questions():
    assert len(_QUESTIONS["bm"]) == len(_QUESTIONS["en"]) == len(_QUESTIONS["zh"])


# ── Mandarin synthesis ───────────────────────────────────────────────────────

async def test_synthesiser_instructs_the_model_to_answer_in_chinese_for_zh():
    seen: dict[str, str] = {}

    async def fake_stream(prompt: str, system_prompt: str):
        seen["system"] = system_prompt
        yield "好"

    with patch.object(syn, "_stream_ilmu", fake_stream):
        _ = [e async for e in syn.synthesiser_node({"language": "zh", "matched_grants": []})]
    assert "简体中文" in seen["system"]


# ── Mandarin stacking advice (the response model used to reject "zh") ────────

def test_advice_and_fallbacks_are_available_in_chinese_for_every_branch():
    advice = _advice("zh", 1, 1, 1, ["X Grant"], True)
    assert len(advice) == 5 and all(_CJK.search(line) for line in advice)
    assert "X Grant" in advice[3]
    assert _CJK.search(_advice("zh", 0, 0, 0, [], False)[0])
    for verdict in ("conflict", "stackable", "unknown"):
        assert _CJK.search(_fallback_explanation(verdict, "zh"))


def test_english_and_malay_advice_are_unchanged():
    assert _advice("en", 0, 0, 0, [], False) == ["All pairs are stackable based on current records."]
    assert _advice("bm", 0, 0, 0, [], False) == ["Semua pasangan boleh ditindan berdasarkan rekod semasa."]


def test_compatibility_endpoint_accepts_zh_and_returns_zh():
    from unittest.mock import AsyncMock, MagicMock

    sb = MagicMock()
    chain = MagicMock()
    chain.select.return_value.in_.return_value.execute = AsyncMock(return_value=MagicMock(data=[]))
    sb.table.return_value = chain

    app = FastAPI()
    app.include_router(eligibility_router.router)
    app.state.supabase = sb
    res = TestClient(app).post(
        "/api/v1/eligibility/compatibility",
        json={"programme_names": ["CIP Spark", "CIP Sprint"], "language": "zh"},
    )
    assert res.status_code == 200, res.text  # was a response-validation error before
    body = res.json()
    assert body["language"] == "zh"
    assert all(_CJK.search(line) for line in body["advice"])


async def test_compatibility_check_in_chinese_never_defaults_unknown_to_stackable():
    from unittest.mock import AsyncMock, MagicMock

    sb = MagicMock()
    chain = MagicMock()
    chain.select.return_value.in_.return_value.execute = AsyncMock(return_value=MagicMock(data=[]))
    sb.table.return_value = chain
    result = await grant_compatibility_check(["CIP Spark", "CIP Sprint"], sb, language="zh")
    assert result["pairs"][0]["verdict"] == "unknown"
    assert _CJK.search(result["pairs"][0]["explanation"])


# ── Required documents ───────────────────────────────────────────────────────

def test_documents_are_validated_and_truncated():
    raw = [
        {"name_en": "SSM registration", "name_bm": "Pendaftaran SSM", "name_zh": "SSM 注册证明"},
        {"name_en": "  Bank statements  "},
        "Audited accounts",
        {"name_en": ""},                       # empty -> dropped
        {"other": "x"},                        # no name key -> dropped
        42,                                    # not an object -> dropped
        {"name_en": "x" * 500},                # truncated
    ]
    out = _normalise_documents(raw)
    assert out[0] == {"name_en": "SSM registration", "name_bm": "Pendaftaran SSM", "name_zh": "SSM 注册证明"}
    assert out[1] == {"name_en": "Bank statements"}
    assert out[2] == {"name_en": "Audited accounts"}
    assert len(out) == 4 and len(out[3]["name_en"]) == 200


def test_documents_are_capped():
    assert len(_normalise_documents([{"name_en": f"d{i}"} for i in range(50)])) == 20


@pytest.mark.parametrize("bad", [None, "SSM", {"name_en": "x"}, 7, [], [[]]])
def test_malformed_or_missing_documents_become_an_empty_list(bad):
    assert _normalise_documents(bad) == []


def test_scored_grant_carries_documents_and_our_last_verified_date():
    grant = {**GRANT, "last_verified": "2026-09-30",
             "required_documents": [{"name_en": "SSM registration"}]}
    out = _score_grant(grant, PROFILE)
    assert out["required_documents"] == [{"name_en": "SSM registration"}]
    assert out["last_verified"] == "2026-09-30"


def test_grant_without_the_column_yet_is_still_scored_before_migration_055():
    out = _score_grant(dict(GRANT), PROFILE)  # no required_documents / last_verified keys
    assert out["required_documents"] == []
    assert out["last_verified"] is None
    assert out["programme_name"] == "CIP Spark"
