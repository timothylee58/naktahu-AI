"""Immigration Navigator nodes — conversational intake + immigration RAG."""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.immigration_navigator.state import ImmigrationState
from app.agents.tools import llm_complete, query_rag_findings

_MAX_TURNS = 5


def _extract_field(text: str, patterns: list[str]) -> str | None:
    lower = text.lower()
    for p in patterns:
        m = re.search(p, lower, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


async def intake_node(state: ImmigrationState) -> dict[str, Any]:
    turns = int(state.get("turns_count") or 0) + 1
    messages = list(state.get("messages") or [])
    if state.get("message"):
        messages.append(state["message"])

    combined = " ".join(messages)
    nationality = state.get("nationality") or _extract_field(
        combined, [r"from\s+(\w+)", r"warganegara\s+(\w+)", r"国籍[：:]?\s*(\w+)"]
    )
    purpose = state.get("purpose") or _extract_field(
        combined,
        [r"(work|study|marry|retire|mm2h|employment pass)", r"(kerja|belajar|berkahwin|persara)"],
    )
    duration = state.get("duration_months")
    if duration is None:
        dm = re.search(r"(\d+)\s*(month|bulan|年)", combined, re.IGNORECASE)
        if dm:
            duration = int(dm.group(1))

    has_deps = state.get("has_dependents")
    if has_deps is None and any(w in combined.lower() for w in ("family", "spouse", "anak", "isteri", "家属")):
        has_deps = True

    missing: list[str] = []
    if not nationality:
        missing.append("nationality")
    if not purpose:
        missing.append("travel purpose")
    if duration is None:
        missing.append("intended stay duration")

    intake_complete = not missing or turns >= _MAX_TURNS
    next_prompt: str | None = None
    if not intake_complete:
        if "nationality" in missing:
            next_prompt = "What is your nationality? / Apakah warganegara anda?"
        elif "travel purpose" in missing:
            next_prompt = "What is the purpose of your stay (work, study, MM2H, etc.)?"
        else:
            next_prompt = "How long do you intend to stay in Malaysia (in months)?"

    return {
        "messages": messages,
        "nationality": nationality,
        "purpose": purpose,
        "duration_months": duration,
        "has_dependents": has_deps,
        "intake_complete": intake_complete,
        "next_prompt": next_prompt,
        "turns_count": turns,
        "status": "needs_input" if not intake_complete else "intake_done",
    }


async def immigration_rag_node(state: ImmigrationState) -> dict[str, Any]:
    lang = state.get("language") or "bm"
    query = (
        f"visa Malaysia {state.get('nationality', '')} {state.get('purpose', '')} "
        f"{state.get('duration_months', '')} months dependents {state.get('has_dependents', False)}"
    )
    hop1 = await query_rag_findings(query, "immigration", lang)
    hop2 = await query_rag_findings(f"requirements checklist {state.get('purpose', '')} Malaysia", "immigration", lang)
    findings = hop1 + [f for f in hop2 if f.get("source_url") not in {h.get("source_url") for h in hop1}]
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "query_rag", "domain": "immigration", "hops": 2})
    return {"_rag_findings": findings, "tool_calls": tool_calls}


async def output_node(state: ImmigrationState) -> dict[str, Any]:
    findings = state.get("_rag_findings") or []
    lang = state.get("language") or "bm"
    context = "\n".join(f"- {f['summary']}" for f in findings[:4])
    purpose = (state.get("purpose") or "visit").lower()

    visa_map = {
        "work": "Employment Pass (EP)",
        "study": "Student Pass",
        "mm2h": "Malaysia My Second Home (MM2H)",
        "marry": "Long-Term Social Visit Pass (spouse)",
        "retire": "MM2H / Retirement visa",
    }
    visa_type = next((v for k, v in visa_map.items() if k in purpose), "Social Visit Pass / Special Pass")

    raw = await llm_complete(
        "You are a Malaysian immigration assistant. Return JSON with keys: checklist (array of strings), warnings (array of strings).",
        f"Visa type hint: {visa_type}\nProfile: {state}\nSources:\n{context}",
        language=lang,
    )
    checklist = [
        "Valid passport (6+ months validity)",
        "Completed immigration form",
        "Supporting documents per visa category",
    ]
    warnings = [
        "Immigration rules change — verify on official imi.gov.my before applying.",
        "This is not legal advice.",
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
            "ministry": "Jabatan Imigresen",
            "confidence": float(f.get("similarity", 0.7)),
        }
        for f in findings[:3]
        if f.get("source_url")
    ]
    return {
        "visa_type": visa_type,
        "checklist": checklist,
        "warnings": warnings,
        "citations": citations,
        "status": "completed",
    }


def route_after_intake(state: ImmigrationState) -> str:
    if state.get("intake_complete"):
        return "immigration_rag"
    return "__end__"
