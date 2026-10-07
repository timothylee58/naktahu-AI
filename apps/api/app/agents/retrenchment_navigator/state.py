"""Retrenchment Navigator state."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class RetrenchmentState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    message: str
    messages: list[str]
    termination_date: Optional[str]
    notice_given_days: Optional[int]
    years_of_service: Optional[float]
    monthly_salary_myr: Optional[float]
    is_eis_contributor: Optional[bool]
    intake_complete: bool
    next_prompt: Optional[str]
    turns_count: int
    eis_eligibility: dict[str, Any]
    statutory_benefits: dict[str, Any]
    notice_period_status: str
    checklist: list[str]
    warnings: list[str]
    citations: list[dict[str, Any]]
    _rag_findings: list[dict[str, Any]]
    status: str
    tool_calls: list[dict[str, Any]]
