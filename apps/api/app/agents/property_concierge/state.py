"""Property Concierge state."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class PropertyConciergeState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    message: str
    messages: list[str]
    purpose: Optional[str]  # "buy" | "rent"
    property_type: Optional[str]  # "condo" | "apartment" | "landed"
    location: Optional[str]
    budget_myr: Optional[float]
    bedrooms: Optional[int]
    intake_complete: bool
    next_prompt: Optional[str]
    turns_count: int
    lead_tier: str  # "hot" | "warm" | "cold" — deterministic, see score_lead()
    search_criteria: dict[str, Any]
    checklist: list[str]
    warnings: list[str]
    escalation_message: str
    citations: list[dict[str, Any]]
    _rag_findings: list[dict[str, Any]]
    status: str
    tool_calls: list[dict[str, Any]]
