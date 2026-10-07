"""Immigration Navigator nodes — conversational intake + immigration RAG,
plus two additive tracks for named JIM (Jabatan Imigresen Malaysia)
e-services and SPO enquiries.

Scope note (see the conversation this shipped from): neither new track
submits anything to imigresen-online.imi.gov.my or eapp.imi.gov.my on a
user's behalf. That would require handling a user's real government-portal
credentials server-side and almost certainly violates those portals' own
Terms of Service — a legal/compliance call this codebase has no standing
to make unilaterally, and no browser-automation dependency exists here for
it anyway. Instead:

- The 6 named e-services (MDAC, ePLKS, MM2H, foreign worker/maid, MyOnline
  Passport, PVIP) get a guided intake that outputs a "ready to copy"
  ordered reference (service_output_node) plus a direct link to the real
  portal — the user pastes it into the actual form themselves, with their
  own login.
- SPO gets a classify-and-draft node (spo_output_node) that produces the
  enquiry category/subcategory and draft text — the user submits it
  themselves at the real SPO portal.

Field schemas below are commonly-required fields for each service, not a
verified byte-for-byte replica of the live form (this sandbox's network
egress proxy blocks direct fetch to imi.gov.my domains — same restriction
documented throughout scripts/sources.py). Every service's warnings list
says so explicitly and tells the user to verify the final field set on the
real portal before submitting.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.immigration_navigator.state import ImmigrationState
from app.agents.tools import llm_complete, query_rag_findings

_MAX_TURNS = 5
_MAX_SERVICE_TURNS = 8
_MAX_SPO_TURNS = 4


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


# ── Named e-service reference-generation track ──────────────────────────

# URLs confirmed real via WebSearch against the actual imi.gov.my/
# imigresen-online.imi.gov.my/eapp.imi.gov.my domains — not content-verified
# via direct fetch (sandbox egress restriction, see module docstring).
# Deliberately excludes "eservices.imi.gov.my.esarvice.online", which
# surfaced in one search result — that's the real eservices.imi.gov.my
# domain suffixed onto an unrelated host, the classic lookalike-domain
# pattern; never link it, ever.
SERVICE_PORTALS: dict[str, dict[str, str]] = {
    "mdac": {
        "name": "Malaysia Digital Arrival Card (MDAC)",
        "url": "https://imigresen-online.imi.gov.my/mdac/main",
        "note": "Submit within 3 days before arrival. Only ever use this exact URL — fake MDAC lookalike sites have been reported by JIM.",
    },
    "eplks": {
        "name": "ePLKS Renewal (myIMMs@JIM)",
        "url": "https://imigresen-online.imi.gov.my/myimms/main",
        "note": "For RENEWAL/payment of an existing PLKS (foreign worker/maid permit). New PLKS applications go through FWCMS (fwcms.com.my) as of Feb 2025, not this portal.",
    },
    "mm2h": {
        "name": "Malaysia My Second Home (eMM2H@JIM)",
        "url": "https://imigresen-online.imi.gov.my/eservices/main",
        "note": "Select the MM2H application type after logging in on the eServices hub.",
    },
    "foreign_worker": {
        "name": "Foreign Worker/Maid Status & Enquiry (MyIMMs)",
        "url": "https://eservices.imi.gov.my/myimms/PRAStatus?type=36&lang=en",
        "note": "Status-check/enquiry portal for an existing foreign worker or maid permit. New applications go through FWCMS (fwcms.com.my), a separate government-linked platform, not this portal.",
    },
    "passport": {
        "name": "MyOnline Passport",
        "url": "https://imigresen-online.imi.gov.my/eservices/myPasport",
        "note": "Malaysian citizens only — passport renewal.",
    },
    "pvip": {
        "name": "Malaysia Premium Visa Programme (PVIP)",
        "url": "https://imigresen-online.imi.gov.my/eservices/main",
        "note": "PVIP applications must go through a JIM-authorised agency, not a self-service form — this reference is what to bring to that agency, not something you submit yourself.",
    },
}

# Commonly-required fields per service, in roughly the order the real form
# asks for them — not a verified exhaustive replica (see module docstring).
SERVICE_FIELD_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "mdac": [
        ("full_name", "Full name, exactly as printed in your passport"),
        ("passport_number", "Passport number"),
        ("nationality", "Nationality"),
        ("flight_or_transport_number", "Flight/transport number"),
        ("arrival_date", "Arrival date in Malaysia"),
        ("accommodation_address", "Accommodation address in Malaysia"),
    ],
    "eplks": [
        ("plks_number", "Existing PLKS number"),
        ("employer_name", "Employer name"),
        ("worker_full_name", "Worker's full name, as in passport"),
        ("passport_number", "Worker's passport number"),
        ("expiry_date", "Current PLKS expiry date"),
    ],
    "mm2h": [
        ("full_name", "Full name, as in passport"),
        ("nationality", "Nationality"),
        ("age", "Age"),
        ("monthly_offshore_income", "Monthly offshore income (MYR)"),
        ("liquid_assets", "Liquid assets (MYR)"),
        ("dependents", "Number of dependents to be included"),
    ],
    "foreign_worker": [
        ("plks_or_application_number", "PLKS number or application reference number"),
        ("worker_full_name", "Worker's full name, as in passport"),
        ("employer_name", "Employer name"),
        ("enquiry_reason", "What you need to check or resolve"),
    ],
    "passport": [
        ("full_name", "Full name, as in MyKad/current passport"),
        ("mykad_number", "MyKad (IC) number"),
        ("current_passport_number", "Current passport number, if renewing"),
        ("reason", "Reason (renewal, lost/damaged, pages full)"),
    ],
    "pvip": [
        ("full_name", "Full name, as in passport"),
        ("nationality", "Nationality"),
        ("age", "Age"),
        ("monthly_offshore_income", "Monthly offshore income (MYR)"),
        ("dependents", "Number of dependents to be included"),
        ("appointed_agency", "Your JIM-authorised agency, if already appointed"),
    ],
}

# Keyword classifier — same lightweight approach as router_node.py's own
# domain detection (Trap #6 note there applies: this is its own local copy,
# not shared, since this agent doesn't import the full chat routing path).
_SERVICE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mdac": ("mdac", "arrival card", "digital arrival"),
    "eplks": ("eplks", "e-plks", "plks", "perpanjang plks"),
    "mm2h": ("mm2h", "second home", "rumah kedua"),
    "foreign_worker": ("foreign worker", "foreign maid", "pembantu rumah asing", "pekerja asing", "maid status", "worker status"),
    "passport": ("myonline passport", "renew passport", "passport renewal", "pasport", "renew my passport"),
    "pvip": ("pvip", "premium visa"),
}
_SPO_KEYWORDS = ("spo", "sistem pertanyaan", "enquiry", "complaint", "aduan", "pertanyaan", "kemuka soalan")


def detect_service_type(text: str) -> str | None:
    lower = text.lower()
    for service, kws in _SERVICE_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            return service
    return None


def is_spo_request(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _SPO_KEYWORDS)


async def service_router_node(state: ImmigrationState) -> dict[str, Any]:
    """First node in the graph — classifies the OPENING message into one of
    the 6 named e-service tracks, the SPO enquiry track, or leaves
    service_type unset (falls through to the original general visa-intake
    flow, unchanged).

    Every continue turn re-enters the graph at START too (see
    continue_immigration_navigator's own comment on why — no interrupt()
    in this graph shape), so this must only classify once: on turn 1. On
    later turns it's a no-op — returning {} leaves the checkpointed
    service_type from turn 1 untouched, rather than re-classifying a
    field-answer message (e.g. an MM2H income figure) and silently
    reassigning the whole conversation to a different track mid-flow."""
    if state.get("turns_count"):
        return {}
    text = state.get("message") or ""
    if is_spo_request(text):
        return {"service_type": "spo"}
    detected = detect_service_type(text)
    return {"service_type": detected}


def route_after_service_detection(state: ImmigrationState) -> str:
    service_type = state.get("service_type")
    if service_type == "spo":
        return "spo_intake"
    if service_type in SERVICE_FIELD_SCHEMAS:
        return "service_intake"
    return "intake"


async def service_intake_node(state: ImmigrationState) -> dict[str, Any]:
    service_type = state.get("service_type") or ""
    schema = SERVICE_FIELD_SCHEMAS.get(service_type, [])
    turns = int(state.get("turns_count") or 0) + 1
    messages = list(state.get("messages") or [])
    if state.get("message"):
        messages.append(state["message"])

    fields = dict(state.get("service_fields") or {})
    # First message classified the service — it isn't itself an answer to
    # a field prompt, so field-filling starts from the *next* message.
    answerable_messages = messages[1:] if len(messages) > 1 else []
    for field_key, _prompt in schema:
        if field_key in fields:
            continue
        idx = len(fields)
        if idx < len(answerable_messages):
            fields[field_key] = answerable_messages[idx].strip()

    missing = [key for key, _ in schema if key not in fields]
    intake_complete = not missing or turns >= _MAX_SERVICE_TURNS
    next_prompt = None
    if not intake_complete:
        next_prompt = next(prompt for key, prompt in schema if key == missing[0])

    return {
        "messages": messages,
        "service_fields": fields,
        "intake_complete": intake_complete,
        "next_prompt": next_prompt,
        "turns_count": turns,
        "status": "needs_input" if not intake_complete else "intake_done",
    }


def route_after_service_intake(state: ImmigrationState) -> str:
    if state.get("intake_complete"):
        return "service_output"
    return "__end__"


async def service_output_node(state: ImmigrationState) -> dict[str, Any]:
    service_type = state.get("service_type") or ""
    schema = SERVICE_FIELD_SCHEMAS.get(service_type, [])
    fields = state.get("service_fields") or {}
    portal = SERVICE_PORTALS.get(service_type, {})
    lang = state.get("language") or "bm"

    prefilled_reference = [
        {"field": prompt, "value": fields.get(key, "")}
        for key, prompt in schema
    ]

    findings = await query_rag_findings(f"{portal.get('name', service_type)} requirements Malaysia", "immigration", lang)
    citations = [
        {
            "title": f.get("source_title", ""),
            "url": f.get("source_url", ""),
            "ministry": "Jabatan Imigresen",
            "confidence": float(f.get("similarity", 0.7)),
        }
        for f in findings[:2]
        if f.get("source_url")
    ]

    warnings = [
        f"This reference lists commonly-required fields for {portal.get('name', service_type)} — verify the exact field set on the official portal before submitting.",
        "NakTahu does not submit this form on your behalf — copy these values into the real portal yourself, using your own login.",
    ]
    if portal.get("note"):
        warnings.append(portal["note"])

    return {
        "prefilled_reference": prefilled_reference,
        "portal_url": portal.get("url", ""),
        "portal_note": portal.get("name", service_type),
        "checklist": [f"{p['field']}: {p['value'] or '(not provided — fill in manually)'}" for p in prefilled_reference],
        "warnings": warnings,
        "citations": citations,
        "status": "completed",
    }


# ── SPO (Sistem Pertanyaan Online) enquiry-drafting track ───────────────

_SPO_PORTAL_URL = "https://eapp.imi.gov.my/spo"

_SPO_CATEGORIES: dict[str, tuple[str, ...]] = {
    "visa_status": ("visa status", "application status", "status permohonan"),
    "foreign_worker_plks": ("plks", "foreign worker", "foreign maid", "pekerja asing", "pembantu rumah"),
    "passport": ("passport", "pasport"),
    "mm2h": ("mm2h", "second home"),
    "general": (),
}


def _classify_enquiry_category(text: str) -> tuple[str, str]:
    lower = text.lower()
    for category, kws in _SPO_CATEGORIES.items():
        if category == "general":
            continue
        if any(kw in lower for kw in kws):
            return category, "general enquiry"
    return "general", "general enquiry"


async def spo_intake_node(state: ImmigrationState) -> dict[str, Any]:
    turns = int(state.get("turns_count") or 0) + 1
    messages = list(state.get("messages") or [])
    if state.get("message"):
        messages.append(state["message"])
    combined = " ".join(messages)

    category, subcategory = _classify_enquiry_category(combined)

    # SPO needs: what happened (the enquiry itself) + contact info the
    # department can reply to. The classifying first message already
    # counts as "what happened" once we have at least one more message
    # confirming/expanding it — kept deliberately short (2 turns max
    # beyond classification) since this is drafting an enquiry, not a
    # full intake form.
    missing: list[str] = []
    if len(messages) < 2:
        missing.append("details")

    intake_complete = not missing or turns >= _MAX_SPO_TURNS
    next_prompt = None
    if not intake_complete:
        next_prompt = "Please describe your enquiry in more detail — what happened, and what response are you looking for?"

    return {
        "messages": messages,
        "enquiry_category": category,
        "enquiry_subcategory": subcategory,
        "intake_complete": intake_complete,
        "next_prompt": next_prompt,
        "turns_count": turns,
        "status": "needs_input" if not intake_complete else "intake_done",
    }


def route_after_spo_intake(state: ImmigrationState) -> str:
    if state.get("intake_complete"):
        return "spo_output"
    return "__end__"


async def spo_output_node(state: ImmigrationState) -> dict[str, Any]:
    lang = state.get("language") or "bm"
    combined = " ".join(state.get("messages") or [])
    category = state.get("enquiry_category", "general")

    raw = await llm_complete(
        "You are drafting a formal enquiry for Malaysia's Immigration Department Sistem Pertanyaan Online (SPO). "
        "Return JSON with key: draft (a single string — a polite, specific enquiry in the user's own language, "
        "3-6 sentences, stating the facts given and what response is being requested). "
        "Do not invent facts, case numbers, or dates not given by the user.",
        f"Enquiry category: {category}\nUser's messages: {combined}",
        language=lang,
    )
    draft = combined  # honest fallback: the user's own words, verbatim, if the LLM call fails
    if raw:
        try:
            parsed = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            draft = parsed.get("draft") or draft
        except (json.JSONDecodeError, ValueError):
            pass

    return {
        "enquiry_draft": draft,
        "checklist": [
            f"Enquiry category: {category}",
            f"Submit at: {_SPO_PORTAL_URL}",
            "Use a valid, active email and phone number — JIM replies through those.",
        ],
        "warnings": [
            "NakTahu does not submit this enquiry on your behalf — copy the draft into the SPO portal yourself.",
            "This is not legal advice; for a disputed or urgent matter, contact JIM directly.",
        ],
        "citations": [],
        "status": "completed",
    }
