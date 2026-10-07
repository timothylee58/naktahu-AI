"""Compliance Drafter LangGraph nodes."""
from __future__ import annotations

from html import escape as _esc
from typing import Any

import structlog

from app.agents.compliance_drafter.state import ComplianceDrafterState
from langchain_core.runnables import RunnableConfig

from app.agents.runtime import supabase_from_config
from app.agents.tools import query_rag_freshness

log = structlog.get_logger(__name__)

# Each section searches the corpus domain that actually holds its content. This
# map used to send tax and EPF to "finance" and business to "government", but
# those domains predate migration 016 (which added tax/epf/business) and hold no
# chunks: production has tax, business and epf content and NONE under finance or
# government, so every section of every report came back empty.
_DOMAIN_MAP = {
    "tax": "tax",
    "business": "business",
    "epf": "epf",
}

# An empty section must say so. A bare heading with nothing under it reads as
# "no obligations here", which on a compliance report is the dangerous reading.
_NO_SOURCES = {
    "bm": "Tiada sumber rasmi dijumpai untuk bahagian ini lagi. Semak terus dengan agensi berkaitan.",
    "en": "No official source was found for this section yet. Check directly with the relevant agency.",
    "zh": "此部分暂未找到官方来源，请直接向相关机构核实。",
}


# Dates shown next to findings. Only dates the corpus actually carries are
# printed; a finding with no date shows nothing rather than an invented one.
_IN_EFFECT_FROM = {
    "bm": "Berkuat kuasa mulai {date}",
    "en": "In effect from {date}",
    "zh": "自 {date} 起生效",
}
_MAY_BE_OUTDATED = {
    "bm": "Mungkin sudah lapuk (bertarikh {date}); sahkan dengan agensi berkaitan.",
    "en": "May be outdated (dated {date}); verify with the agency.",
    "zh": "可能已过时（日期：{date}），请向相关机构核实。",
}
# A rule announced for the future is NOT a current obligation, so it is listed
# under its own sub-heading and never mixed into the section's main list.
_ANNOUNCED_HEADING = {
    "bm": "Perubahan yang diumumkan (belum berkuat kuasa)",
    "en": "Announced changes (not yet in effect)",
    "zh": "已公布的变更（尚未生效）",
}
_TAKES_EFFECT = {
    "bm": "Akan berkuat kuasa pada {date}",
    "en": "Takes effect on {date}",
    "zh": "生效日期：{date}",
}
_ANNOUNCED_ON = {
    "bm": "Diumumkan pada {date}",
    "en": "Announced on {date}",
    "zh": "公布日期：{date}",
}


def _t(table: dict[str, str], language: str) -> str:
    return table.get(language, table["bm"])


def _dated(table: dict[str, str], language: str, date_value: Any) -> str:
    """Escaped, localized "<label> <date>" text; "" when there is no date."""
    date_text = str(date_value or "").strip()
    if not date_text:
        return ""
    return _esc(_t(table, language).format(date=date_text))


def _finding_li(f: dict[str, Any], language: str, *, announced: bool = False) -> str:
    """One list item. Current findings show "In effect from" and, when stale,
    the outdated warning; announced ones show when they take effect."""
    notes: list[str] = []
    if announced:
        notes += [
            _dated(_TAKES_EFFECT, language, f.get("effective_date")),
            _dated(_ANNOUNCED_ON, language, f.get("announced_date")),
        ]
    else:
        notes.append(_dated(_IN_EFFECT_FROM, language, f.get("effective_date")))
        if f.get("stale"):
            notes.append(_dated(
                _MAY_BE_OUTDATED, language, f.get("stale_ref_date") or f.get("effective_date")
            ))
    meta = "".join(f"<br><em>{n}</em>" for n in notes if n)
    return (
        f"<li><strong>{_esc(f.get('source_title', ''))}</strong>: "
        f"{_esc((f.get('summary') or '')[:300])}"
        f"{_link(f.get('source_url', ''))}{meta}</li>"
    )


def _link(url: str) -> str:
    """An anchor for a real http(s) URL, else "" — a missing or non-web URL is
    omitted rather than rendered as an empty or javascript: link."""
    url = (url or "").strip()
    if not url.lower().startswith(("https://", "http://")):
        return ""
    return f" <a href='{_esc(url, quote=True)}'>{_esc(url)}</a>"


async def intake_node(state: ComplianceDrafterState) -> dict[str, Any]:
  """Capture business profile from start/continue payload."""
  turns = int(state.get("turns_count") or 0) + 1
  business_type = state.get("business_type") or "sole_proprietor"
  domains = state.get("domains") or ["tax", "business", "epf"]
  return {
      "business_type": business_type,
      "domains": domains,
      "intake_complete": True,
      "turns_count": turns,
      "language": state.get("language") or "bm",
  }


async def _search_section(state: ComplianceDrafterState, key: str, query: str) -> dict[str, Any]:
    """Search one section's corpus domain and keep only what is in force today.

    ``{key}_findings`` holds current rules; ``{key}_announced`` holds rules that
    are announced but not yet in effect; superseded and expired rows are
    dropped (counted in ``{key}_dropped``). All values are plain JSON types so
    the state checkpoints.
    """
    result = await query_rag_freshness(query, _DOMAIN_MAP[key], state.get("language", "bm"))
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({
        "tool": "query_rag",
        "domain": key,
        "hits": len(result["current"]),
        "announced": len(result["announced"]),
        "superseded_dropped": result["dropped"]["superseded"],
        "expired_dropped": result["dropped"]["expired"],
    })
    return {
        f"{key}_findings": result["current"],
        f"{key}_announced": result["announced"],
        f"{key}_dropped": result["dropped"],
        "tool_calls": tool_calls,
    }


async def query_tax_node(state: ComplianceDrafterState) -> dict[str, Any]:
  if "tax" not in (state.get("domains") or []):
      return {"tax_findings": [], "tax_announced": []}
  query = f"cukai pendapatan pematuhan {state.get('business_type', '')} {state.get('context', '')}"
  return await _search_section(state, "tax", query)


async def query_business_node(state: ComplianceDrafterState) -> dict[str, Any]:
  if "business" not in (state.get("domains") or []):
      return {"business_findings": [], "business_announced": []}
  query = f"SSM pendaftaran pematuhan perniagaan {state.get('business_type', '')} {state.get('context', '')}"
  return await _search_section(state, "business", query)


async def query_epf_node(state: ComplianceDrafterState) -> dict[str, Any]:
  if "epf" not in (state.get("domains") or []):
      return {"epf_findings": [], "epf_announced": []}
  query = f"KWSP EPF caruman majikan {state.get('business_type', '')} {state.get('context', '')}"
  return await _search_section(state, "epf", query)


async def compile_node(state: ComplianceDrafterState) -> dict[str, Any]:
  """Assemble HITL preview report from domain findings."""
  sections: list[dict[str, Any]] = []
  requested = state.get("domains") or ["tax", "business", "epf"]
  for domain, label in [
      ("tax", "Tax (LHDN)"),
      ("business", "Business (SSM)"),
      ("epf", "EPF/KWSP"),
  ]:
      # A section the user did not ask for is left out. Rendering it would say
      # "no official source was found" for a topic nobody searched.
      if domain not in requested:
          continue
      findings = list(state.get(f"{domain}_findings") or [])
      announced = list(state.get(f"{domain}_announced") or [])
      sections.append({
          "title": label,
          # "findings" is kept for existing readers; "current" is the same list
          # under its explicit name, next to "announced" (not yet in effect).
          "findings": findings,
          "current": findings,
          "announced": announced,
          "dropped": dict(state.get(f"{domain}_dropped") or {}),
      })

  report_json: dict[str, Any] = {
      "business_type": state.get("business_type"),
      "domains": state.get("domains"),
      "sections": sections,
      "disclaimer": (
          "This report is AI-generated from official-source RAG retrieval. "
          "Verify with a licensed professional before filing."
      ),
  }

  language = state.get("language") or "bm"
  no_sources = _NO_SOURCES.get(language, _NO_SOURCES["bm"])
  # Everything interpolated below can carry markup (business_type is user input;
  # titles and summaries come from ingested documents), and the HTML is rendered
  # to PDF server-side, so it is escaped.
  html_parts = [
      "<html><head><meta charset='utf-8'><title>Compliance Report</title></head><body>",
      f"<h1>Compliance Report — {_esc(str(state.get('business_type') or 'Business'))}</h1>",
  ]
  for sec in sections:
      html_parts.append(f"<h2>{_esc(sec['title'])}</h2>")
      # Empty only when there is neither a current nor an announced finding.
      if not sec["findings"] and not sec["announced"]:
          html_parts.append(f"<ul><li><em>{_esc(no_sources)}</em></li></ul>")
      if sec["findings"]:
          html_parts.append("<ul>")
          html_parts.extend(_finding_li(f, language) for f in sec["findings"])
          html_parts.append("</ul>")
      if sec["announced"]:
          # Never mixed into the list above: not yet in force.
          html_parts.append(f"<h3>{_esc(_t(_ANNOUNCED_HEADING, language))}</h3><ul>")
          html_parts.extend(_finding_li(f, language, announced=True) for f in sec["announced"])
          html_parts.append("</ul>")
  html_parts.append(f"<p><em>{_esc(report_json['disclaimer'])}</em></p></body></html>")

  return {
      "report_sections": sections,
      "report_json": report_json,
      "report_html": "".join(html_parts),
      "awaiting_hitl": True,
  }


async def generate_pdf_node(state: ComplianceDrafterState, config: RunnableConfig | None = None) -> dict[str, Any]:
  from app.agents.tools import generate_pdf as gen_pdf

  supabase = supabase_from_config(config)  # run-scoped, not checkpointed
  path, url, expires = await gen_pdf(
      state.get("report_html") or "<p>Empty report</p>",
      user_id=state.get("user_id") or "unknown",
      supabase_client=supabase,
  )
  tool_calls = list(state.get("tool_calls") or [])
  tool_calls.append({"tool": "generate_pdf", "path": path})
  return {
      "pdf_storage_path": path,
      "signed_url": url,
      "url_expires_at": expires or None,
      "awaiting_hitl": False,
      "tool_calls": tool_calls,
  }


async def notify_node(state: ComplianceDrafterState) -> dict[str, Any]:
  from app.agents.tools import send_email

  email = state.get("_user_email")
  sent = False
  if email and state.get("signed_url"):
      sent = await send_email(
          to=email,
          subject="Your NakTahu Compliance Report",
          html_body=(
              f"<p>Your compliance report is ready.</p>"
              f"<p><a href='{_esc(str(state.get('signed_url')), quote=True)}'>Download PDF</a></p>"
          ),
      )
  tool_calls = list(state.get("tool_calls") or [])
  tool_calls.append({"tool": "send_email", "sent": sent})
  return {"email_sent": sent, "tool_calls": tool_calls}
