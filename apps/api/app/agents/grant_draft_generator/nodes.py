"""Grant Draft Generator LangGraph nodes.

CRITICAL correctness property (see CLAUDE.md's citation-URL and
confidence-gate rules for the same category of concern): the financial
projection section is a SKELETON — a structured template for the founder
to fill in — never real, verified numbers. Every section and its HTML/JSON
rendering must make that unambiguous.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.agents.grant_draft_generator.state import GrantDraftState
from app.agents.tools import llm_complete

log = structlog.get_logger(__name__)

_SKELETON_DISCLAIMER_EN = (
    "TEMPLATE ONLY — not real financial data. Every figure below is a "
    "placeholder for you (or your accountant) to replace with your own "
    "verified numbers before submission."
)
_SKELETON_DISCLAIMER_BM = (
    "TEMPLAT SAHAJA — bukan data kewangan sebenar. Setiap angka di bawah "
    "adalah tempat letak untuk anda (atau akauntan anda) gantikan dengan "
    "angka sebenar yang disahkan sebelum penyerahan."
)

_REPORT_DISCLAIMER_EN = (
    "This draft is AI-generated and is a starting point only. Verify all "
    "figures, eligibility details, and required documents against the "
    "grant agency's actual application guidelines before submission."
)
_REPORT_DISCLAIMER_BM = (
    "Draf ini dijana oleh AI dan hanya merupakan titik permulaan. Sahkan "
    "semua angka, butiran kelayakan, dan dokumen yang diperlukan mengikut "
    "garis panduan permohonan sebenar agensi geran sebelum penyerahan."
)

_DOCUMENT_CHECKLIST_BASE: list[dict[str, Any]] = [
    {
        "item": "SSM Registration Certificate",
        "description": "Current Companies Commission of Malaysia (SSM) business/company registration certificate.",
        "required": True,
    },
    {
        "item": "LHDN Tax Compliance Letter",
        "description": "Letter of good standing / tax compliance status from Lembaga Hasil Dalam Negeri (LHDN).",
        "required": True,
    },
    {
        "item": "Audited or Management Accounts",
        "description": (
            "Audited financial statements for the last 1-2 years. If the business is "
            "under 24 months old, management accounts (unaudited) are typically accepted instead."
        ),
        "required": True,
    },
    {
        "item": "Business Plan Outline",
        "description": "A concise business plan covering the problem, solution, market, team, and use of grant funds.",
        "required": True,
    },
]


async def intake_node(state: GrantDraftState) -> dict[str, Any]:
    """Capture selected grant + business profile from the start payload."""
    turns = int(state.get("turns_count") or 0) + 1
    return {
        "programme_name": state.get("programme_name") or "",
        "business_profile": state.get("business_profile") or {},
        "language": state.get("language") or "bm",
        "export_format": state.get("export_format") or "pdf",
        "turns_count": turns,
    }


async def fetch_grant_node(state: GrantDraftState) -> dict[str, Any]:
    """Look up the selected grant in `grant_database`. Degrades gracefully:
    a missing programme or unavailable Supabase sets `error` and downstream
    nodes no-op rather than crashing the graph (CLAUDE.md Trap #4 spirit)."""
    programme_name = state.get("programme_name") or ""
    supabase = state.get("_supabase")

    if not programme_name:
        return {"error": "programme_name is required", "grant_record": None}

    if supabase is None:
        return {"error": "Grant database is temporarily unavailable.", "grant_record": None}

    try:
        res = await (
            supabase.table("grant_database")
            .select("*")
            .eq("programme_name", programme_name)
            .limit(1)
            .execute()
        )
        rows = res.data or []
    except Exception as exc:
        log.warning("grant_database_lookup_failed", error=str(exc), programme=programme_name)
        return {"error": "Grant database is temporarily unavailable.", "grant_record": None}

    if not rows:
        return {"error": f"Grant programme not found: {programme_name}", "grant_record": None}

    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "fetch_grant", "programme": programme_name, "found": True})
    return {"grant_record": rows[0], "error": None, "tool_calls": tool_calls}


def _financial_skeleton(grant_record: dict[str, Any], language: str) -> dict[str, Any]:
    """Build a structured, clearly-labeled financial projection TEMPLATE.
    Numbers are placeholders ("0.00" / null), never fabricated figures."""
    amount_min = grant_record.get("amount_min_myr")
    amount_max = grant_record.get("amount_max_myr")
    disclaimer = _SKELETON_DISCLAIMER_BM if language == "bm" else _SKELETON_DISCLAIMER_EN
    return {
        "is_template": True,
        "disclaimer": disclaimer,
        "grant_amount_range_myr": {"min": amount_min, "max": amount_max},
        "revenue_projection": [
            {"period": "Year 1", "projected_revenue_myr": None, "notes": "Fill in with your own forecast"},
            {"period": "Year 2", "projected_revenue_myr": None, "notes": "Fill in with your own forecast"},
            {"period": "Year 3", "projected_revenue_myr": None, "notes": "Fill in with your own forecast"},
        ],
        "cost_breakdown": [
            {"category": "Manpower / salaries", "amount_myr": None},
            {"category": "Equipment / capex", "amount_myr": None},
            {"category": "Marketing / customer acquisition", "amount_myr": None},
            {"category": "Operations / overheads", "amount_myr": None},
            {"category": "Other", "amount_myr": None},
        ],
        "funding_allocation": [
            {"use_of_funds": "Describe how the grant amount will be allocated", "amount_myr": None},
        ],
    }


async def draft_node(state: GrantDraftState) -> dict[str, Any]:
    """Generate the four report sections. Narrative sections use llm_complete
    grounded in the fetched grant_record + business_profile; the financial
    section is templated (see _financial_skeleton), not LLM-hallucinated."""
    if state.get("error"):
        return {}

    grant = state.get("grant_record") or {}
    profile = state.get("business_profile") or {}
    language = state.get("language") or "bm"

    grant_context = (
        f"Grant: {grant.get('programme_name', '')} ({grant.get('agency', '')}). "
        f"Type: {grant.get('grant_type', '')}. "
        f"Amount range: RM{grant.get('amount_min_myr', 'N/A')} - RM{grant.get('amount_max_myr', 'N/A')}. "
        f"Eligible sectors: {grant.get('eligible_sectors', [])}. "
        f"Notes: {grant.get('notes_bm' if language == 'bm' else 'notes_en', '') or grant.get('notes_en', '')}"
    )
    business_context = (
        f"Business type: {profile.get('business_type', '')}. Sector: {profile.get('sector', '')}. "
        f"Registered for {profile.get('registered_months', 'unknown')} months. "
        f"Annual revenue: RM{profile.get('annual_revenue_myr', 'unknown')}. "
        f"Bumiputera-owned: {profile.get('is_bumiputera', 'unknown')}."
    )

    executive_summary = await llm_complete(
        "You are drafting a grant application executive summary for a Malaysian SME. "
        "Write 2-3 concise paragraphs introducing the business and why it is a strong "
        "fit for this specific grant. Do not invent financial figures.",
        f"{grant_context}\n\n{business_context}",
        language=language,
        max_tokens=400,
    )
    if not executive_summary:
        executive_summary = (
            f"[Draft pending] Executive summary for {profile.get('business_type', 'the business')} "
            f"applying to {grant.get('programme_name', 'the selected grant')}."
        )

    use_of_funds_narrative = await llm_complete(
        "You are drafting the use-of-funds narrative section of a Malaysian grant "
        "application. Describe, in prose, the categories of spend the grant would "
        "fund (e.g. manpower, equipment, marketing) in a way consistent with this "
        "grant's stated purpose. Do not state specific ringgit amounts as fact — "
        "refer the reader to the financial projection template for figures they must fill in.",
        f"{grant_context}\n\n{business_context}",
        language=language,
        max_tokens=400,
    )
    if not use_of_funds_narrative:
        use_of_funds_narrative = (
            "[Draft pending] Describe how the grant funds will be allocated across "
            "manpower, equipment, marketing, and operations. See the financial "
            "projection template below for the figures to fill in."
        )

    financial_projection_skeleton = _financial_skeleton(grant, language)
    document_checklist = [dict(item) for item in _DOCUMENT_CHECKLIST_BASE]

    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "llm_complete", "sections": ["executive_summary", "use_of_funds_narrative"]})

    return {
        "executive_summary": executive_summary,
        "use_of_funds_narrative": use_of_funds_narrative,
        "financial_projection_skeleton": financial_projection_skeleton,
        "document_checklist": document_checklist,
        "tool_calls": tool_calls,
    }


def _render_financial_html(skeleton: dict[str, Any]) -> str:
    parts = [
        f"<p><strong>{skeleton.get('disclaimer', '')}</strong></p>",
        "<h3>Revenue Projection (template)</h3><ul>",
    ]
    for row in skeleton.get("revenue_projection", []):
        parts.append(f"<li>{row.get('period')}: RM_____ ({row.get('notes')})</li>")
    parts.append("</ul><h3>Cost Breakdown (template)</h3><ul>")
    for row in skeleton.get("cost_breakdown", []):
        parts.append(f"<li>{row.get('category')}: RM_____</li>")
    parts.append("</ul><h3>Funding Allocation (template)</h3><ul>")
    for row in skeleton.get("funding_allocation", []):
        parts.append(f"<li>{row.get('use_of_funds')}: RM_____</li>")
    parts.append("</ul>")
    return "".join(parts)


async def compile_node(state: GrantDraftState) -> dict[str, Any]:
    """Assemble report_html/report_json and set awaiting_hitl for user approval
    before generation/billing (mirrors compliance_drafter's compile_node)."""
    if state.get("error"):
        return {
            "report_json": {"error": state["error"]},
            "report_html": f"<html><body><p>{state['error']}</p></body></html>",
            "awaiting_hitl": False,
        }

    language = state.get("language") or "bm"
    grant = state.get("grant_record") or {}
    disclaimer = _REPORT_DISCLAIMER_BM if language == "bm" else _REPORT_DISCLAIMER_EN
    skeleton = state.get("financial_projection_skeleton") or {}

    report_json: dict[str, Any] = {
        "programme_name": grant.get("programme_name"),
        "agency": grant.get("agency"),
        "executive_summary": state.get("executive_summary"),
        "use_of_funds_narrative": state.get("use_of_funds_narrative"),
        "financial_projection_skeleton": skeleton,
        "document_checklist": state.get("document_checklist") or [],
        "disclaimer": disclaimer,
    }

    html_parts = [
        "<html><head><meta charset='utf-8'><title>Grant Application Draft</title></head><body>",
        f"<h1>Grant Application Draft — {grant.get('programme_name', '')}</h1>",
        f"<p><em>{disclaimer}</em></p>",
        "<h2>Executive Summary</h2>",
        f"<p>{state.get('executive_summary', '')}</p>",
        "<h2>Use of Funds</h2>",
        f"<p>{state.get('use_of_funds_narrative', '')}</p>",
        "<h2>Financial Projection Skeleton</h2>",
        _render_financial_html(skeleton),
        "<h2>Required Document Checklist</h2><ul>",
    ]
    for doc in state.get("document_checklist") or []:
        req = "Required" if doc.get("required") else "Optional"
        html_parts.append(f"<li><strong>{doc.get('item')}</strong> ({req}): {doc.get('description')}</li>")
    html_parts.append(f"</ul><p><em>{disclaimer}</em></p></body></html>")

    return {
        "report_json": report_json,
        "report_html": "".join(html_parts),
        "awaiting_hitl": True,
    }


async def generate_export_node(state: GrantDraftState) -> dict[str, Any]:
    if state.get("error"):
        return {"awaiting_hitl": False}

    supabase = state.get("_supabase")
    export_format = state.get("export_format") or "pdf"
    html = state.get("report_html") or "<p>Empty report</p>"
    user_id = state.get("user_id") or "unknown"
    tool_calls = list(state.get("tool_calls") or [])

    if export_format == "docx":
        from app.agents.tools import generate_docx as gen_docx

        path, url, expires = await gen_docx(
            state.get("report_json") or {},
            user_id=user_id,
            agent_type="grant-draft-generator",
            supabase_client=supabase,
        )
        tool_calls.append({"tool": "generate_docx", "path": path})
        return {
            "docx_storage_path": path,
            "signed_url": url,
            "url_expires_at": expires or None,
            "awaiting_hitl": False,
            "tool_calls": tool_calls,
        }

    from app.agents.tools import generate_pdf as gen_pdf

    path, url, expires = await gen_pdf(
        html,
        user_id=user_id,
        agent_type="grant-draft-generator",
        supabase_client=supabase,
    )
    tool_calls.append({"tool": "generate_pdf", "path": path})
    return {
        "pdf_storage_path": path,
        "signed_url": url,
        "url_expires_at": expires or None,
        "awaiting_hitl": False,
        "tool_calls": tool_calls,
    }


async def notify_node(state: GrantDraftState) -> dict[str, Any]:
    from app.agents.tools import send_email

    if state.get("error"):
        return {"email_sent": False}

    email = state.get("_user_email")
    sent = False
    if email and state.get("signed_url"):
        sent = await send_email(
            to=email,
            subject="Your NakTahu Grant Application Draft",
            html_body=(
                "<p>Your grant application draft is ready.</p>"
                f"<p><a href='{state.get('signed_url')}'>Download</a></p>"
                "<p>Remember: verify all figures and required documents before submission.</p>"
            ),
        )
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "send_email", "sent": sent})
    return {"email_sent": sent, "tool_calls": tool_calls}
