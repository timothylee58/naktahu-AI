"""Eligibility Agent state — multi-turn business grant-eligibility matching.

Supersedes grant_finder (single-shot) with a conversational intake ->
hybrid RAG -> scoring/near-miss/stacking-matrix -> streamed-summary
pipeline. See CLAUDE.md Trap #6 for the shared _VALID_DOMAINS list this
agent's grant_rag_node must stay inside (government/finance/education —
no new domain needed).
"""
from __future__ import annotations

from typing import Any, TypedDict


class BusinessProfile(TypedDict, total=False):
    business_type: str            # sole_prop|sdn_bhd|startup|llp|cooperative
    registered_months: int
    sector: str
    sub_sector: str
    annual_revenue_myr: float
    is_bumiputera: bool
    employee_count: int
    has_md_status: bool           # Malaysia Digital status
    existing_grants: list[str]
    is_pre_revenue: bool
    is_sme: bool


class EligibilityState(TypedDict, total=False):
    session_id: str
    user_id: str | None
    language: str
    current_turn: int
    messages: list[dict[str, Any]]
    latest_user_input: str
    business_profile: BusinessProfile | None
    intake_complete: bool
    missing_fields: list[str]
    next_question: str | None
    retrieved_grant_chunks: list[dict[str, Any]]
    structured_grants: list[dict[str, Any]]
    matched_grants: list[dict[str, Any]]
    near_miss_grants: list[dict[str, Any]]
    stacking_matrix: dict[str, Any] | None
    summary_bm: str
    summary_en: str
    streaming_token_buffer: str
    needs_more_info: bool
    needs_clarification: bool
    error: str | None
    # Internal, stripped from any public-facing output (see agent_runner._public_output)
    _supabase: Any
