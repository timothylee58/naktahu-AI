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

    # ── Named e-service reference-generation track (MDAC/ePLKS/MM2H/
    # foreign-worker/passport/PVIP) — see nodes.py's SERVICE_* maps and
    # module docstring for why this generates a copy-paste reference
    # rather than submitting anything.
    service_type: Optional[str]
    service_fields: dict[str, str]
    prefilled_reference: list[dict[str, str]]
    portal_url: str
    portal_note: str

    # ── SPO (Sistem Pertanyaan Online) enquiry-drafting track.
    enquiry_category: str
    enquiry_subcategory: str
    enquiry_draft: str
