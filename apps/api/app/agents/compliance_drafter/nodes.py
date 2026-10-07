"""Compliance Drafter LangGraph nodes."""
from __future__ import annotations

from html import escape as _esc
from typing import Any

import structlog

from app.agents.compliance_drafter.state import ComplianceDrafterState
from langchain_core.runnables import RunnableConfig

from app.agents.runtime import supabase_from_config
from app.agents.tools import query_rag_findings

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


async def query_tax_node(state: ComplianceDrafterState) -> dict[str, Any]:
  if "tax" not in (state.get("domains") or []):
      return {"tax_findings": []}
  query = f"cukai pendapatan pematuhan {state.get('business_type', '')} {state.get('context', '')}"
  findings = await query_rag_findings(query, _DOMAIN_MAP["tax"], state.get("language", "bm"))
  tool_calls = list(state.get("tool_calls") or [])
  tool_calls.append({"tool": "query_rag", "domain": "tax", "hits": len(findings)})
  return {"tax_findings": findings, "tool_calls": tool_calls}


async def query_business_node(state: ComplianceDrafterState) -> dict[str, Any]:
  if "business" not in (state.get("domains") or []):
      return {"business_findings": []}
  query = f"SSM pendaftaran pematuhan perniagaan {state.get('business_type', '')} {state.get('context', '')}"
  findings = await query_rag_findings(query, _DOMAIN_MAP["business"], state.get("language", "bm"))
  tool_calls = list(state.get("tool_calls") or [])
  tool_calls.append({"tool": "query_rag", "domain": "business", "hits": len(findings)})
  return {"business_findings": findings, "tool_calls": tool_calls}


async def query_epf_node(state: ComplianceDrafterState) -> dict[str, Any]:
  if "epf" not in (state.get("domains") or []):
      return {"epf_findings": []}
  query = f"KWSP EPF caruman majikan {state.get('business_type', '')} {state.get('context', '')}"
  findings = await query_rag_findings(query, _DOMAIN_MAP["epf"], state.get("language", "bm"))
  tool_calls = list(state.get("tool_calls") or [])
  tool_calls.append({"tool": "query_rag", "domain": "epf", "hits": len(findings)})
  return {"epf_findings": findings, "tool_calls": tool_calls}


async def compile_node(state: ComplianceDrafterState) -> dict[str, Any]:
  """Assemble HITL preview report from domain findings."""
  sections: list[dict[str, Any]] = []
  requested = state.get("domains") or ["tax", "business", "epf"]
  for domain, label, key in [
      ("tax", "Tax (LHDN)", "tax_findings"),
      ("business", "Business (SSM)", "business_findings"),
      ("epf", "EPF/KWSP", "epf_findings"),
  ]:
      # A section the user did not ask for is left out. Rendering it would say
      # "no official source was found" for a topic nobody searched.
      if domain not in requested:
          continue
      findings = state.get(key) or []
      sections.append({"title": label, "findings": findings})

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
      html_parts.append(f"<h2>{_esc(sec['title'])}</h2><ul>")
      if not sec["findings"]:
          html_parts.append(f"<li><em>{_esc(no_sources)}</em></li>")
      for f in sec["findings"]:
          html_parts.append(
              f"<li><strong>{_esc(f.get('source_title', ''))}</strong>: "
              f"{_esc((f.get('summary') or '')[:300])}"
              f"{_link(f.get('source_url', ''))}</li>"
          )
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
