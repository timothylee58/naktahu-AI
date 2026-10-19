"""Health Triage nodes — structured symptom intake + KKM RAG + facility recommendation."""
from __future__ import annotations

import re
from typing import Any

from app.agents.health_triage.state import EMERGENCY_SYMPTOM_IDS, HEALTH_SYMPTOM_IDS, HealthTriageState
from app.agents.tools import llm_complete, query_rag_findings

_DISCLAIMER = {
    "bm": (
        "⚠️ Ini BUKAN diagnosis perubatan. Sila dapatkan rawatan segera di klinik/hospital "
        "jika simptom teruk. Untuk kecemasan, hubungi 999."
    ),
    "en": (
        "⚠️ This is NOT a medical diagnosis. Seek immediate care at a clinic/hospital "
        "if symptoms are severe. For emergencies, call 999."
    ),
    "zh": (
        "⚠️ 这不是医疗诊断。如果症状严重，请立即前往诊所或医院。"
        "紧急情况请拨打 999。"
    ),
}

# Legacy message-only callers (no chip ids). Kept for direct API use.
# Not applied when the wizard sent structured fields — the composed
# sentence always contains the symptom label ("sakit dada"), which would
# mark a mild, red-flag-negative report as an emergency.
_URGENT_KEYWORDS = frozenset({
    "sakit dada", "sesak nafas", "pening teruk", "pendarahan", "hilang kesedaran",
    "chest pain", "difficulty breathing", "severe bleeding", "unconscious",
})

_RECOMMENDATION = {
    "emergency": {
        "bm": "Hubungi 999 sekarang. Pergi ke bilik kecemasan hospital kerajaan (A&E) dengan segera.",
        "en": "Call 999 now. Go to the nearest government hospital emergency department (A&E) immediately.",
        "zh": "请立即拨打 999，并前往最近的政府医院急诊室（A&E）。",
    },
    "clinic": {
        "bm": "Lawati klinik kesihatan atau klinik swasta hari ini.",
        "en": "Visit a government health clinic or a private clinic today.",
        "zh": "请今天前往政府诊所或私人诊所就诊。",
    },
    "monitor": {
        "bm": "Pantau di rumah dan rehat. Dapatkan rawatan jika simptom bertambah teruk.",
        "en": "Rest and monitor at home. Seek care if the symptoms get worse.",
        "zh": "请在家休息并观察。如果症状加重，请就医。",
    },
}

_ALLOWED_SYMPTOMS = frozenset(HEALTH_SYMPTOM_IDS)


def _language(state: HealthTriageState) -> str:
    lang = state.get("language") or "bm"
    return lang if lang in _DISCLAIMER else "en"


def _clean_symptom_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: list[str] = []
    for item in raw:
        if isinstance(item, str) and item in _ALLOWED_SYMPTOMS and item not in seen:
            seen.append(item)
    return seen[:10]


def _clean_red_flags(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, bool] = {}
    for key, value in raw.items():
        if isinstance(key, str) and key in _ALLOWED_SYMPTOMS and isinstance(value, bool):
            cleaned[key] = value
        if len(cleaned) >= 10:
            break
    return cleaned


def classify_urgency(state: HealthTriageState) -> str:
    """Return emergency, clinic, or monitor.

    Structured wizard fields win. A red-flag yes, or severe chest pain /
    breathlessness, is always emergency. Keyword scanning is only the
    fallback for a message that arrived without those fields.
    """
    red_flags = _clean_red_flags(state.get("red_flags"))
    if any(red_flags.values()):
        return "emergency"

    symptom_ids = _clean_symptom_ids(state.get("symptom_ids"))
    reported = state.get("reported_severity") or ""
    structured = bool(symptom_ids) or reported in {"mild", "moderate", "severe"} or bool(red_flags)
    if structured:
        if reported == "severe" and any(symptom_id in EMERGENCY_SYMPTOM_IDS for symptom_id in symptom_ids):
            return "emergency"
        if reported == "mild":
            return "monitor"
        return "clinic"

    text = (state.get("message") or "").lower()
    if any(keyword in text for keyword in _URGENT_KEYWORDS):
        return "emergency"
    return "clinic"


def _facility_rows(urgency: str, lang: str) -> list[dict[str, str]]:
    if urgency == "emergency":
        action = {
            "bm": "Hubungi 999 jika perlukan ambulans",
            "en": "Call 999 if you need an ambulance",
            "zh": "如需救护车请拨打 999",
        }[lang]
        name = {
            "bm": "Jabatan Kecemasan hospital kerajaan",
            "en": "Government hospital emergency department",
            "zh": "政府医院急诊室",
        }[lang]
        return [{"type": "hospital_ed", "name": name, "action": action}]

    if urgency == "monitor":
        action = {
            "bm": "Pergi jika simptom bertambah teruk",
            "en": "Go if symptoms get worse",
            "zh": "如果症状加重再前往",
        }[lang]
        return [{"type": "klinik_kesihatan", "name": "Klinik Kesihatan", "action": action}]

    kk_action = {
        "bm": "Walk-in atau tempah melalui MySejahtera",
        "en": "Walk-in or book via MySejahtera",
        "zh": "可直接就诊，或通过 MySejahtera 预约",
    }[lang]
    gp_action = {
        "bm": "Klinik swasta jika perlukan akses lebih cepat",
        "en": "Private clinic for faster access",
        "zh": "私人诊所，就诊通常更快",
    }[lang]
    gp_name = "General practitioner (GP)" if lang == "en" else "Klinik swasta (GP)"
    return [
        {"type": "klinik_kesihatan", "name": "Klinik Kesihatan", "action": kk_action},
        {"type": "klinik_swasta", "name": gp_name, "action": gp_action},
    ]


def _blocks_escalation(extra: str) -> bool:
    """A non-emergency note must not tell the user to call emergency services."""
    lower = extra.lower()
    return "999" in extra or "kecemasan" in lower or "emergency" in lower or "紧急" in extra


async def symptom_intake_node(state: HealthTriageState) -> dict[str, Any]:
    text = (state.get("message") or "").strip()
    parts = re.split(r"[,;.\n]+", text)
    symptoms = [part.strip() for part in parts if len(part.strip()) > 2][:8]
    if not symptoms and text:
        symptoms = [text]

    symptom_ids = _clean_symptom_ids(state.get("symptom_ids"))
    red_flags = _clean_red_flags(state.get("red_flags"))
    urgency = classify_urgency({**state, "symptom_ids": symptom_ids, "red_flags": red_flags})
    return {
        "symptoms": symptoms,
        "symptom_ids": symptom_ids,
        "red_flags": red_flags,
        "body_area": state.get("body_area") or "",
        "duration": state.get("duration") or "",
        "reported_severity": state.get("reported_severity") or "",
        "severity": "urgent" if urgency == "emergency" else "routine",
        "urgency": urgency,
        "language": _language(state),
    }


async def kkm_rag_node(state: HealthTriageState) -> dict[str, Any]:
    lang = _language(state)
    symptom_ids = state.get("symptom_ids") or []
    subject = " ".join(symptom_ids) if symptom_ids else " ".join(state.get("symptoms") or [])
    query = f"simptom {subject} rawatan klinik kesihatan Malaysia"
    findings = await query_rag_findings(query, "healthcare", lang)
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "query_rag", "domain": "healthcare", "hits": len(findings)})
    return {"_rag_findings": findings, "tool_calls": tool_calls}


async def facility_node(state: HealthTriageState) -> dict[str, Any]:
    lang = _language(state)
    urgency = state.get("urgency") or classify_urgency(state)
    if urgency not in _RECOMMENDATION:
        urgency = "clinic"
    findings = state.get("_rag_findings") or []
    rec = _RECOMMENDATION[urgency][lang]

    # The emergency sentence is fixed. A retrieved chunk must not replace
    # "call 999" with a softer one-line summary.
    context = findings[0]["summary"] if findings else ""
    if urgency != "emergency" and context:
        extra = await llm_complete(
            "Add one short sentence of public-health context. Do not contradict the recommendation, do not diagnose, and do not mention 999 or emergency care.",
            f"Recommendation: {rec}\nSymptoms: {state.get('symptom_ids') or state.get('symptoms')}\nGuidance: {context}",
            language=lang,
            max_tokens=120,
        )
        if extra and not _blocks_escalation(extra):
            rec = f"{rec} {extra.strip()}"

    citations = [
        {
            "title": finding.get("source_title", ""),
            "url": finding.get("source_url", ""),
            "ministry": "KKM",
            "confidence": 0.75,
        }
        for finding in findings[:2]
        if finding.get("source_url")
    ]
    return {
        "urgency": urgency,
        "facility_recommendation": rec,
        "facilities": _facility_rows(urgency, lang),
        "citations": citations,
        "status": "completed",
    }


async def disclaimer_node(state: HealthTriageState) -> dict[str, Any]:
    return {"disclaimer": _DISCLAIMER[_language(state)]}
