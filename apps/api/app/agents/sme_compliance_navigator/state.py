"""SME Compliance Navigator (PatuhiKu) — LangGraph state."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ComplianceNavigatorState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    business_profile: str  # free text: structure, revenue, headcount, recent events
    triggered_domains: list[str]  # subset of ["tax", "payroll", "corporate"]
    # Annotated[..., operator.add] — parallel-safe reducer; each Send()-dispatched
    # subagent node appends its own single-element list, LangGraph merges them.
    domain_results: Annotated[list[dict[str, Any]], operator.add]
    checklist: list[dict[str, Any]]
    stale_warnings: list[str]
    tool_calls: list[dict[str, Any]]
