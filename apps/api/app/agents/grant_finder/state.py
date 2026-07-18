"""Grant Finder state — recommended civic agent for government funding discovery."""
from __future__ import annotations

from typing import Any, TypedDict


class GrantFinderState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    sector: str
    business_stage: str
    funding_need: str
    message: str
    grants: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    _rag_findings: list[dict[str, Any]]
    status: str
    tool_calls: list[dict[str, Any]]
