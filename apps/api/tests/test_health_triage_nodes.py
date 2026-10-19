"""Structured health-triage urgency. The wizard's chip ids decide the
destination; the localized display sentence must not override them, and
an emergency recommendation must not be rewritten by the model."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.agents.health_triage.nodes import classify_urgency, disclaimer_node, facility_node, symptom_intake_node
from app.routers.agents import AgentStartRequest


def test_red_flag_yes_is_emergency_even_when_the_message_is_chinese() -> None:
    urgency = classify_urgency({
        "language": "zh",
        "message": "胸痛，轻度",
        "symptom_ids": ["sakit_dada"],
        "reported_severity": "mild",
        "red_flags": {"sakit_dada": True},
    })
    assert urgency == "emergency"


def test_mild_chest_pain_with_red_flag_no_stays_monitor() -> None:
    """The composed sentence contains 'sakit dada', which the old keyword
    list treated as urgent. Structured 'no' must keep the home-monitor path."""
    urgency = classify_urgency({
        "message": "Sakit dada sejak < 1 hari, tahap keterukan: Ringan. Sakit dada tidak merebak.",
        "symptom_ids": ["sakit_dada"],
        "reported_severity": "mild",
        "red_flags": {"sakit_dada": False},
    })
    assert urgency == "monitor"


def test_severe_chest_pain_is_emergency_without_a_red_flag_yes() -> None:
    urgency = classify_urgency({
        "symptom_ids": ["sakit_dada"],
        "reported_severity": "severe",
        "red_flags": {"sakit_dada": False},
    })
    assert urgency == "emergency"


def test_severe_fever_without_red_flag_is_clinic_today() -> None:
    urgency = classify_urgency({
        "symptom_ids": ["demam"],
        "reported_severity": "severe",
        "red_flags": {"demam": False},
    })
    assert urgency == "clinic"


def test_legacy_message_without_chips_still_catches_chest_pain() -> None:
    assert classify_urgency({"message": "chest pain since this morning"}) == "emergency"
    assert classify_urgency({"message": "demam sejak semalam"}) == "clinic"


@pytest.mark.asyncio
async def test_intake_records_urgency_and_keeps_display_symptoms() -> None:
    result = await symptom_intake_node({
        "message": "Demam for < 1 day, severity: Mild.",
        "language": "en",
        "symptom_ids": ["demam"],
        "reported_severity": "mild",
        "red_flags": {"demam": False},
        "body_area": "general",
        "duration": "less_1",
    })
    assert result["urgency"] == "monitor"
    assert result["severity"] == "routine"
    assert result["symptom_ids"] == ["demam"]
    assert "Demam" in result["symptoms"][0]


@pytest.mark.asyncio
async def test_emergency_recommendation_is_fixed_and_skips_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = AsyncMock(side_effect=AssertionError("llm must not run for an emergency"))
    monkeypatch.setattr("app.agents.health_triage.nodes.llm_complete", llm)
    result = await facility_node({
        "language": "zh",
        "urgency": "emergency",
        "symptom_ids": ["sakit_dada"],
        "_rag_findings": [{
            "summary": "Klinik kesihatan untuk rawatan primer.",
            "source_title": "Klinik Kesihatan",
            "source_url": "https://www.moh.gov.my/",
        }],
    })
    assert "999" in result["facility_recommendation"]
    assert "急诊" in result["facility_recommendation"]
    assert result["facilities"][0]["type"] == "hospital_ed"
    assert result["citations"][0]["url"] == "https://www.moh.gov.my/"
    llm.assert_not_called()


@pytest.mark.asyncio
async def test_clinic_note_appends_context_but_drops_a_999_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agents.health_triage.nodes.llm_complete",
        AsyncMock(return_value="Call 999 and go to emergency now."),
    )
    result = await facility_node({
        "language": "en",
        "urgency": "clinic",
        "symptom_ids": ["demam"],
        "_rag_findings": [{"summary": "Outpatient fee is RM1 for citizens.", "source_url": "https://www.moh.gov.my/", "source_title": "MOH"}],
    })
    assert result["facility_recommendation"] == "Visit a government health clinic or a private clinic today."
    assert "999" not in result["facility_recommendation"]


@pytest.mark.asyncio
async def test_clinic_note_keeps_a_non_emergency_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.agents.health_triage.nodes.llm_complete",
        AsyncMock(return_value="Citizens pay RM1 per outpatient visit."),
    )
    result = await facility_node({
        "language": "en",
        "urgency": "monitor",
        "_rag_findings": [{"summary": "fee", "source_url": "https://www.moh.gov.my/", "source_title": "MOH"}],
    })
    assert result["facility_recommendation"].startswith("Rest and monitor at home.")
    assert "RM1" in result["facility_recommendation"]


@pytest.mark.asyncio
async def test_chinese_disclaimer() -> None:
    result = await disclaimer_node({"language": "zh"})
    assert "不是医疗诊断" in result["disclaimer"]
    assert "999" in result["disclaimer"]


def test_start_request_rejects_an_unknown_symptom_and_red_flag() -> None:
    with pytest.raises(ValidationError):
        AgentStartRequest(symptom_ids=["not_a_symptom"])
    with pytest.raises(ValidationError):
        AgentStartRequest(red_flags={"invented": True})
    body = AgentStartRequest(
        symptom_ids=["sakit_dada"],
        reported_severity="mild",
        red_flags={"sakit_dada": False},
        body_area="chest",
        duration="less_1",
    )
    assert body.symptom_ids == ["sakit_dada"]
