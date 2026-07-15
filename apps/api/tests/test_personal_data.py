"""Tests for app.agents.personal_data — personal-record query detection."""
from __future__ import annotations

from app.agents.personal_data import detect_personal_data_agency


def test_detects_epf_balance_query():
    result = detect_personal_data_agency("What is my EPF balance?", domain="epf")
    assert result is not None
    assert result["agency"] == "KWSP / EPF"
    assert result["portal"] == "https://www.kwsp.gov.my"


def test_detects_epf_balance_query_bm():
    result = detect_personal_data_agency("Berapa baki saya dalam akaun KWSP?", domain="epf")
    assert result is not None
    assert result["agency"] == "KWSP / EPF"


def test_detects_tax_refund_status():
    result = detect_personal_data_agency("What's the status of my tax refund?", domain="tax")
    assert result is not None
    assert result["agency"] == "LHDN"


def test_detects_ic_query():
    result = detect_personal_data_agency("I lost my IC, what do I do?", domain="government")
    assert result is not None
    assert result["agency"] == "JPN (Jabatan Pendaftaran Negara)"


def test_ignores_general_rules_question_without_personal_marker():
    assert detect_personal_data_agency("What is the EPF withdrawal age?", domain="epf") is None


def test_ignores_personal_marker_without_domain_keyword_or_matching_domain():
    assert detect_personal_data_agency("I have a question about weather", domain="culture") is None


def test_falls_back_to_router_domain_when_no_keyword_hit():
    result = detect_personal_data_agency("Can you check my account status?", domain="tax")
    assert result is not None
    assert result["agency"] == "LHDN"


def test_empty_query_returns_none():
    assert detect_personal_data_agency("", domain="epf") is None
