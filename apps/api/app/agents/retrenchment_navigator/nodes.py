"""Retrenchment Navigator nodes — conversational intake + legal/epf RAG +
deterministic statutory-benefit calculation.

The statutory termination-benefit figure (Employment Act 1955, Second
Schedule) and the minimum-notice-period figure (Section 12) are exact,
money-adjacent facts — they are computed with plain Python arithmetic in
output_node, never asked of the LLM, so a hallucinated number can never
reach a user asking "how much am I owed." The LLM is only used to draft the
narrative checklist/warnings text around those computed facts.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.retrenchment_navigator.state import RetrenchmentState
from app.agents.tools import llm_complete, query_rag_findings

_MAX_TURNS = 6

# Employment Act 1955, Second Schedule — termination/lay-off benefit rate,
# in days' wages per completed year of service, banded by continuous
# service length.
_TERMINATION_BENEFIT_BANDS = (
    (2, 10),   # < 2 years: 10 days' wages per year
    (5, 15),   # 2 to < 5 years: 15 days' wages per year
    (float("inf"), 20),  # >= 5 years: 20 days' wages per year
)

# Employment Act 1955, Section 12 — minimum notice period absent a longer
# contractual term, banded by continuous service length.
_NOTICE_PERIOD_BANDS = (
    (2, 4),   # < 2 years: 4 weeks
    (5, 6),   # 2 to < 5 years: 6 weeks
    (float("inf"), 8),  # >= 5 years: 8 weeks
)


def _band_lookup(years: float, bands: tuple[tuple[float, int], ...]) -> int:
    for ceiling, value in bands:
        if years < ceiling:
            return value
    return bands[-1][1]


def calculate_statutory_benefits(years_of_service: float, monthly_salary_myr: float) -> dict[str, Any]:
    """Deterministic Employment Act Second Schedule calculation. Pure function — no LLM involved."""
    days_per_year = _band_lookup(years_of_service, _TERMINATION_BENEFIT_BANDS)
    # Employment Act's "ordinary rate of pay" for a daily figure divides the
    # monthly wage by 26 (the Act's standard working-days-per-month divisor).
    daily_wage = monthly_salary_myr / 26
    total_days = round(days_per_year * years_of_service)
    estimated_benefit_myr = round(daily_wage * total_days, 2)
    return {
        "days_per_year_of_service": days_per_year,
        "total_days_owed": total_days,
        "estimated_benefit_myr": estimated_benefit_myr,
        "basis": "Employment Act 1955, Second Schedule (statutory minimum — a contract may specify more, never less)",
    }


def calculate_notice_period_weeks(years_of_service: float) -> int:
    """Deterministic Employment Act Section 12 minimum notice period. Pure function."""
    return _band_lookup(years_of_service, _NOTICE_PERIOD_BANDS)


def _extract_number(text: str, patterns: list[str]) -> float | None:
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


async def intake_node(state: RetrenchmentState) -> dict[str, Any]:
    turns = int(state.get("turns_count") or 0) + 1
    messages = list(state.get("messages") or [])
    if state.get("message"):
        messages.append(state["message"])
    combined = " ".join(messages)

    years_of_service = state.get("years_of_service")
    if years_of_service is None:
        years_of_service = _extract_number(
            combined, [r"(\d+(?:\.\d+)?)\s*(?:years?|tahun|年)"]
        )

    monthly_salary_myr = state.get("monthly_salary_myr")
    if monthly_salary_myr is None:
        monthly_salary_myr = _extract_number(
            combined, [r"(?:rm|myr)\s*([\d,]+(?:\.\d+)?)", r"([\d,]+(?:\.\d+)?)\s*(?:ringgit|a month|sebulan)"]
        )

    notice_given_days = state.get("notice_given_days")
    if notice_given_days is None:
        notice_given_days = _extract_number(
            combined, [r"(\d+)\s*(?:days?|hari)\s*notice", r"notice\s*(?:of)?\s*(\d+)\s*(?:days?|hari)"]
        )

    is_eis_contributor = state.get("is_eis_contributor")
    if is_eis_contributor is None:
        lower = combined.lower()
        if any(w in lower for w in ("eis contributor", "contribute to eis", "socso contributor", "menyumbang eis")):
            is_eis_contributor = True
        elif any(w in lower for w in ("not an eis contributor", "no eis", "tidak menyumbang eis")):
            is_eis_contributor = False

    missing: list[str] = []
    if years_of_service is None:
        missing.append("years_of_service")
    if monthly_salary_myr is None:
        missing.append("monthly_salary")
    if notice_given_days is None:
        missing.append("notice_given")
    if is_eis_contributor is None:
        missing.append("eis_contributor")

    intake_complete = not missing or turns >= _MAX_TURNS
    next_prompt: str | None = None
    if not intake_complete:
        if "years_of_service" in missing:
            next_prompt = "How many years have you worked for this employer? / Berapa lama anda telah bekerja (dalam tahun)?"
        elif "monthly_salary" in missing:
            next_prompt = "What was your last monthly salary (RM)? / Berapakah gaji bulanan terakhir anda (RM)?"
        elif "notice_given" in missing:
            next_prompt = "How many days' notice did your employer give you (0 if none)? / Berapa hari notis yang diberikan majikan anda?"
        else:
            next_prompt = "Were you contributing to EIS/SOCSO through this job? / Adakah anda menyumbang kepada EIS/SOCSO melalui pekerjaan ini?"

    return {
        "messages": messages,
        "years_of_service": years_of_service,
        "monthly_salary_myr": monthly_salary_myr,
        "notice_given_days": notice_given_days,
        "is_eis_contributor": is_eis_contributor,
        "intake_complete": intake_complete,
        "next_prompt": next_prompt,
        "turns_count": turns,
        "status": "needs_input" if not intake_complete else "intake_done",
    }


async def retrenchment_rag_node(state: RetrenchmentState) -> dict[str, Any]:
    """Query both `legal` (termination rights, EIS claims process) and `epf`
    (EIS/SOCSO registration & contribution facts) — the two domains this
    topic was deliberately split across (see migration 030's header)."""
    lang = state.get("language") or "bm"
    query = (
        f"retrenchment termination employee rights notice period "
        f"{state.get('years_of_service', '')} years service Malaysia"
    )
    legal_findings = await query_rag_findings(query, "legal", lang)
    eis_query = "EIS EIS claim unemployment benefit SOCSO PERKESO employer registration"
    epf_findings = await query_rag_findings(eis_query, "epf", lang)
    seen = {f.get("source_url") for f in legal_findings}
    findings = legal_findings + [f for f in epf_findings if f.get("source_url") not in seen]
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "query_rag", "domain": "legal", "hops": 1})
    tool_calls.append({"tool": "query_rag", "domain": "epf", "hops": 1})
    return {"_rag_findings": findings, "tool_calls": tool_calls}


async def output_node(state: RetrenchmentState) -> dict[str, Any]:
    findings = state.get("_rag_findings") or []
    lang = state.get("language") or "bm"
    context = "\n".join(f"- {f['summary']}" for f in findings[:4])

    years = state.get("years_of_service") or 0.0
    salary = state.get("monthly_salary_myr") or 0.0
    notice_given = state.get("notice_given_days") or 0
    is_eis = state.get("is_eis_contributor")

    statutory_benefits = calculate_statutory_benefits(years, salary) if years and salary else {}
    minimum_notice_weeks = calculate_notice_period_weeks(years) if years else None
    minimum_notice_days = minimum_notice_weeks * 7 if minimum_notice_weeks else None
    notice_period_status = "unknown"
    if minimum_notice_days is not None:
        notice_period_status = (
            "sufficient" if notice_given >= minimum_notice_days else "employer owes payment in lieu of notice"
        )

    eis_eligibility: dict[str, Any] = {
        "likely_eligible": bool(is_eis) if is_eis is not None else None,
        "note": (
            "Indicative only — actual eligibility also requires 12 months of EIS contributions "
            "within the last 24 months and that job loss was not due to resignation, misconduct, "
            "or retirement. Confirm via the official PERKESO EIS portal."
        ),
    }

    raw = await llm_complete(
        "You are a Malaysian employment-rights assistant helping someone navigate retrenchment. "
        "Return JSON with keys: checklist (array of strings), warnings (array of strings). "
        "Do not invent specific ringgit amounts or day counts — those are already computed separately.",
        f"Years of service: {years}\nMonthly salary: RM{salary}\nNotice given (days): {notice_given}\n"
        f"Sources:\n{context}",
        language=lang,
    )
    checklist = [
        "Request a written termination letter stating the reason and effective date.",
        "Check whether payment in lieu of notice is owed if notice given was short.",
        "Apply for EIS Job Search Allowance within 60 days of job loss, if eligible.",
        "Keep all payslips and EPF statements as proof of service and salary.",
    ]
    warnings = [
        "This is a statutory-minimum estimate under the Employment Act 1955 — your contract may specify more, never less.",
        "This is not legal advice. For a disputed termination, contact the Labour Department (JTKSM) or a lawyer.",
    ]
    if raw:
        try:
            parsed = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            checklist = parsed.get("checklist") or checklist
            warnings = parsed.get("warnings") or warnings
        except (json.JSONDecodeError, ValueError):
            pass

    citations = [
        {
            "title": f.get("source_title", ""),
            "url": f.get("source_url", ""),
            "ministry": "Jabatan Tenaga Kerja Semenanjung Malaysia (JTKSM) / PERKESO",
            "confidence": float(f.get("similarity", 0.7)),
        }
        for f in findings[:3]
        if f.get("source_url")
    ]
    return {
        "eis_eligibility": eis_eligibility,
        "statutory_benefits": statutory_benefits,
        "notice_period_status": notice_period_status,
        "checklist": checklist,
        "warnings": warnings,
        "citations": citations,
        "status": "completed",
    }


def route_after_intake(state: RetrenchmentState) -> str:
    if state.get("intake_complete"):
        return "retrenchment_rag"
    return "__end__"
