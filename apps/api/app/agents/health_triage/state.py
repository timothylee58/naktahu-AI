"""Health Triage state."""
from __future__ import annotations

from typing import Any, TypedDict


class HealthTriageState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    message: str
    symptoms: list[str]
    severity: str
    facility_recommendation: str
    facilities: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    _rag_findings: list[dict[str, Any]]
    disclaimer: str
    status: str
    tool_calls: list[dict[str, Any]]
