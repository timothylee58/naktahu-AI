"""Health Triage state."""
from __future__ import annotations

from typing import Any, TypedDict

# Chip ids from the health-triage wizard. Urgency is scored from these,
# not from the localized sentence the page also sends for display.
HEALTH_SYMPTOM_IDS: tuple[str, ...] = (
    "demam",
    "batuk",
    "sakit_kepala",
    "pening",
    "sesak_nafas",
    "sakit_dada",
    "sakit_perut",
    "loya",
    "cirit_birit",
    "ruam",
)

# Severe chest pain or breathlessness is an emergency on its own.
# Every other symptom waits for its red-flag answer.
EMERGENCY_SYMPTOM_IDS: frozenset[str] = frozenset({"sakit_dada", "sesak_nafas"})


class HealthTriageState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    message: str
    body_area: str
    symptom_ids: list[str]
    symptoms: list[str]
    duration: str
    reported_severity: str
    red_flags: dict[str, bool]
    severity: str
    urgency: str
    facility_recommendation: str
    facilities: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    _rag_findings: list[dict[str, Any]]
    disclaimer: str
    status: str
    tool_calls: list[dict[str, Any]]
