"""Compliance Drafter LangGraph nodes."""
from __future__ import annotations

from typing import Any

import structlog

from app.agents.compliance_drafter.state import ComplianceDrafterState
from langchain_core.runnables import RunnableConfig

from app.agents.runtime import supabase_from_config
from app.agents.tools import query_rag_findings

log = structlog.get_logger(__name__)

_DOMAIN_MAP = {
    "tax": "finance",
    "business": "government",
    "epf": "finance",
}


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
  for label, key in [
      ("Tax (LHDN)", "tax_findings"),
      ("Business (SSM)", "business_findings"),
      ("EPF/KWSP", "epf_findings"),
  ]:
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

  html_parts = [
      "<html><head><meta charset='utf-8'><title>Compliance Report</title></head><body>",
      f"<h1>Compliance Report — {state.get('business_type', 'Business')}</h1>",
  ]
  for sec in sections:
      html_parts.append(f"<h2>{sec['title']}</h2><ul>")
      for f in sec["findings"]:
          html_parts.append(
              f"<li><strong>{f.get('source_title', '')}</strong>: "
              f"{f.get('summary', '')[:300]} "
              f"<a href='{f.get('source_url', '')}'>{f.get('source_url', '')}</a></li>"
          )
      html_parts.append("</ul>")
  html_parts.append(f"<p><em>{report_json['disclaimer']}</em></p></body></html>")

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
              f"<p><a href='{state.get('signed_url')}'>Download PDF</a></p>"
          ),
      )
  tool_calls = list(state.get("tool_calls") or [])
  tool_calls.append({"tool": "send_email", "sent": sent})
  return {"email_sent": sent, "tool_calls": tool_calls}
