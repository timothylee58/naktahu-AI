"""Immigration Navigator state."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class ImmigrationState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    message: str
    messages: list[str]
    nationality: Optional[str]
    purpose: Optional[str]
    duration_months: Optional[int]
    has_dependents: Optional[bool]
    intake_complete: bool
    next_prompt: Optional[str]
    turns_count: int
    visa_type: str
    checklist: list[str]
    warnings: list[str]
    citations: list[dict[str, Any]]
    _rag_findings: list[dict[str, Any]]
    status: str
    tool_calls: list[dict[str, Any]]
