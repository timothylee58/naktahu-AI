"""Health Triage nodes — BM symptom intake + KKM RAG + facility recommendation."""
from __future__ import annotations

import re
from typing import Any

from app.agents.health_triage.state import HealthTriageState
from app.agents.tools import llm_complete, query_rag_findings

_DISCLAIMER_BM = (
    "⚠️ Ini BUKAN diagnosis perubatan. Sila dapatkan rawatan segera di klinik/hospital "
    "jika simptom teruk. Untuk kecemasan, hubungi 999."
)
_DISCLAIMER_EN = (
    "⚠️ This is NOT a medical diagnosis. Seek immediate care at a clinic/hospital "
    "if symptoms are severe. For emergencies, call 999."
)

_URGENT_KEYWORDS = frozenset({
    "sakit dada", "sesak nafas", "pening teruk", "pendarahan", "hilang kesedaran",
    "chest pain", "difficulty breathing", "severe bleeding", "unconscious",
})


async def symptom_intake_node(state: HealthTriageState) -> dict[str, Any]:
    text = (state.get("message") or "").strip()
    parts = re.split(r"[,;.\n]+", text)
    symptoms = [p.strip() for p in parts if len(p.strip()) > 2][:8]
    if not symptoms and text:
        symptoms = [text]
    lower = text.lower()
    severity = "urgent" if any(k in lower for k in _URGENT_KEYWORDS) else "routine"
    return {
        "symptoms": symptoms,
        "severity": severity,
        "language": state.get("language") or "bm",
    }


async def kkm_rag_node(state: HealthTriageState) -> dict[str, Any]:
    lang = state.get("language") or "bm"
    query = f"simptom {' '.join(state.get('symptoms') or [])} rawatan klinik kesihatan Malaysia"
    findings = await query_rag_findings(query, "healthcare", lang)
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "query_rag", "domain": "healthcare", "hits": len(findings)})
    return {"_rag_findings": findings, "tool_calls": tool_calls}


async def facility_node(state: HealthTriageState) -> dict[str, Any]:
    lang = state.get("language") or "bm"
    severity = state.get("severity") or "routine"
    findings = state.get("_rag_findings") or []

    if severity == "urgent":
        rec = "Hospital kerajaan / GH — pergi ke bilik kecemasan (ED) segera."
        facilities = [
            {"type": "hospital_ed", "name": "Nearest government hospital A&E", "action": "Call 999 if needed"},
        ]
    else:
        rec = "Klinik kesihatan (KK) / Klinik 1Malaysia untuk rawatan primer."
        facilities = [
            {"type": "klinik_kesihatan", "name": "Klinik Kesihatan", "action": "Walk-in or book via MySejahtera"},
            {"type": "klinik_swasta", "name": "General practitioner (GP)", "action": "Private clinic for faster access"},
        ]

    context = findings[0]["summary"] if findings else ""
    if context:
        extra = await llm_complete(
            "Summarise appropriate public healthcare facility type in one sentence.",
            f"Symptoms: {state.get('symptoms')}\nGuidance: {context}",
            language=lang,
            max_tokens=120,
        )
        if extra:
            rec = extra

    citations = [
        {
            "title": f.get("source_title", ""),
            "url": f.get("source_url", ""),
            "ministry": "KKM",
            "confidence": 0.75,
        }
        for f in findings[:2]
        if f.get("source_url")
    ]
    return {
        "facility_recommendation": rec,
        "facilities": facilities,
        "citations": citations,
        "status": "completed",
    }


async def disclaimer_node(state: HealthTriageState) -> dict[str, Any]:
    lang = state.get("language") or "bm"
    return {"disclaimer": _DISCLAIMER_BM if lang == "bm" else _DISCLAIMER_EN}
