"""Compliance Drafter agent state."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class ComplianceDrafterState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    business_type: str
    domains: list[str]
    context: str
    intake_complete: bool
    tax_findings: list[dict[str, Any]]
    business_findings: list[dict[str, Any]]
    epf_findings: list[dict[str, Any]]
    # Announced but not yet in force (effective_date in the future). Kept apart
    # from the *_findings above, which hold only what is in force today.
    tax_announced: list[dict[str, Any]]
    business_announced: list[dict[str, Any]]
    epf_announced: list[dict[str, Any]]
    # {"superseded": n, "expired": n}: rows left out of a section's findings.
    tax_dropped: dict[str, int]
    business_dropped: dict[str, int]
    epf_dropped: dict[str, int]
    report_sections: list[dict[str, Any]]
    report_html: str
    report_json: dict[str, Any]
    pdf_storage_path: str
    signed_url: str
    url_expires_at: Optional[str]
    email_sent: bool
    turns_count: int
    tool_calls: list[dict[str, Any]]
    awaiting_hitl: bool
    error: Optional[str]
    _supabase: Any
    _user_email: Optional[str]
