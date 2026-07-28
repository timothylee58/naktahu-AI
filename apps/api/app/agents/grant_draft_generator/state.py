"""Grant Draft Generator agent state.

Given a selected grant (a `grant_database` row, see
infra/supabase/migrations/020_eligibility_agent.sql) and a business
profile, drafts an executive summary, use-of-funds narrative, financial
projection SKELETON (a template, never presented as real figures — see
draft_node in nodes.py), and a required-document checklist. Mirrors the
compliance_drafter HITL pattern: interrupt_before generate_export so the
user approves the draft body before a real PDF/DOCX is generated and
credits are deducted.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict

# Reuses the eligibility_agent BusinessProfile shape rather than inventing
# a new one (CLAUDE.md: don't duplicate structures the codebase already has).
from app.agents.eligibility_agent.state import BusinessProfile


class GrantDraftState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    programme_name: str
    business_profile: BusinessProfile
    grant_record: Optional[dict[str, Any]]
    executive_summary: str
    use_of_funds_narrative: str
    financial_projection_skeleton: dict[str, Any]
    document_checklist: list[dict[str, Any]]
    report_html: str
    report_json: dict[str, Any]
    export_format: str  # "pdf" | "docx"
    pdf_storage_path: str
    docx_storage_path: str
    signed_url: str
    url_expires_at: Optional[str]
    awaiting_hitl: bool
    email_sent: bool
    turns_count: int
    tool_calls: list[dict[str, Any]]
    error: Optional[str]
    _supabase: Any
    _user_email: Optional[str]
