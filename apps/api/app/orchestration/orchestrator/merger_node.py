"""merger_node — synthesizes multi-agent outputs into a coherent response.

Takes the agent_results from the executor and produces:
- A unified final_output combining insights from all agents
- Deduplicated merged_citations (by URL)
- An overall_confidence score (weighted average)
- Aggregated suggestions from all agents
- Metadata: agents_used, total_latency_ms, output_flagged

For single-agent results, the merger passes through without LLM synthesis.
For multi-agent results, it uses ILMU to weave findings into a coherent
bilingual answer that references each agent's contribution.
"""
from __future__ import annotations

import json
import re
from typing import Any

import structlog

from app.orchestration.orchestrator.state import AgentExecutionResult, OrchestratorState
from app.services.llm_client import ILMU_CHAT_MODEL, ilmu_client

log = structlog.get_logger(__name__)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_MERGER_SYSTEM_PROMPT = """\
You are a synthesis assistant for NakTahu AI, a Malaysian civic knowledge system.

You receive findings from multiple specialist agents that each answered a different \
aspect of the user's query. Your job is to weave them into ONE coherent, well-structured \
answer that:
1. Addresses the user's original query completely
2. Organizes information logically (not just concatenating agent outputs)
3. Removes redundancy while preserving all unique facts
4. Uses clear headings or bullet points for multi-part answers
5. Maintains factual accuracy — never add information not in the findings
6. Cites sources naturally (e.g. "According to LHDN..." or "Based on EPF guidelines...")

LANGUAGE RULE: Answer in the same language as the user's query.
- If query is in Bahasa Malaysia → answer in BM
- If query is in English → answer in English
- If query is in Chinese → answer in Chinese

Do NOT mention "Agent 1", "Agent 2", etc. The user should see a seamless answer.
"""


def _deduplicate_citations(
    all_citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate citations by URL, keeping the highest confidence version."""
    seen_urls: dict[str, dict[str, Any]] = {}
    no_url: list[dict[str, Any]] = []

    for citation in all_citations:
        url = citation.get("url", "")
        if not url:
            no_url.append(citation)
            continue
        existing = seen_urls.get(url)
        if not existing or citation.get("confidence", 0) > existing.get("confidence", 0):
            seen_urls[url] = citation

    # Return URL-deduplicated + no-URL citations, capped at 9
    merged = list(seen_urls.values()) + no_url
    # Sort by confidence descending
    merged.sort(key=lambda c: c.get("confidence", 0), reverse=True)
    return merged[:9]


def _compute_overall_confidence(results: list[AgentExecutionResult]) -> float:
    """Weighted average confidence across completed agent results.

    Failed/timed-out agents contribute 0.0 to pull overall confidence down
    (they represent gaps in the answer).
    """
    if not results:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for r in results:
        status = r.get("status", "failed")
        confidence = r.get("confidence", 0.0)

        if status == "completed":
            weight = 1.0
            weighted_sum += confidence * weight
        else:
            # Failed tasks get weight but 0 confidence
            weight = 0.5

        total_weight += weight

    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0


def _aggregate_suggestions(results: list[AgentExecutionResult]) -> list[str]:
    """Collect unique suggestions from all agents, capped at 5."""
    seen: set[str] = set()
    suggestions: list[str] = []

    for r in results:
        for s in r.get("suggestions", []):
            normalized = s.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                suggestions.append(s.strip())
                if len(suggestions) >= 5:
                    return suggestions

    return suggestions


async def _synthesize_multi_agent(
    query: str,
    language: str,
    results: list[AgentExecutionResult],
) -> str:
    """Use ILMU to merge multiple agent outputs into a coherent answer."""
    # Build context from agent results
    findings_parts: list[str] = []
    for i, r in enumerate(results, 1):
        if r.get("status") != "completed" or not r.get("output"):
            continue
        agent = r.get("agent_name", "unknown")
        output = r.get("output", "")
        # Truncate very long outputs to stay within token limits
        if len(output) > 1500:
            output = output[:1500] + "..."
        findings_parts.append(f"--- Finding {i} (from {agent}) ---\n{output}")

    if not findings_parts:
        return ""

    findings_text = "\n\n".join(findings_parts)

    lang_instruction = {
        "bm": "Jawab dalam Bahasa Malaysia.",
        "zh": "用简体中文回答。",
        "en": "Answer in English.",
    }.get(language, "Answer in English.")

    user_message = (
        f"Original user query: {query}\n\n"
        f"Language instruction: {lang_instruction}\n\n"
        f"Findings from specialist agents:\n\n{findings_text}"
    )

    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _MERGER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1536,
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        log.warning("merger_synthesis_failed", error=str(exc))
        # Fallback: concatenate outputs with headers
        return _fallback_merge(results, language)


def _fallback_merge(results: list[AgentExecutionResult], language: str) -> str:
    """Simple concatenation fallback when LLM synthesis fails."""
    parts: list[str] = []

    for r in results:
        if r.get("status") != "completed" or not r.get("output"):
            continue
        output = r.get("output", "")
        parts.append(output)

    separator = "\n\n---\n\n"
    return separator.join(parts)


async def merger_node(state: OrchestratorState) -> dict[str, Any]:
    """Combine multi-agent results into a unified response.

    For single-agent results, passes through without LLM synthesis.
    For multi-agent results, uses ILMU to produce a coherent merged answer.
    """
    agent_results: list[AgentExecutionResult] = state.get("agent_results", [])
    query = state.get("query", "")
    language = state.get("language", "en")

    if not agent_results:
        log.warning("merger_no_results")
        return {
            "final_output": "",
            "merged_citations": [],
            "overall_confidence": 0.0,
            "suggestions": [],
            "agents_used": [],
            "total_latency_ms": 0.0,
            "output_flagged": False,
        }

    # Collect metadata
    agents_used = list({r.get("agent_name", "") for r in agent_results if r.get("agent_name")})
    total_latency = sum(r.get("latency_ms", 0.0) for r in agent_results)
    output_flagged = any(r.get("output_flagged", False) for r in agent_results)

    # Collect and deduplicate citations
    all_citations: list[dict[str, Any]] = []
    for r in agent_results:
        all_citations.extend(r.get("citations", []))
    merged_citations = _deduplicate_citations(all_citations)

    # Compute confidence
    overall_confidence = _compute_overall_confidence(agent_results)

    # Aggregate suggestions
    suggestions = _aggregate_suggestions(agent_results)

    # Determine synthesis strategy
    completed_results = [r for r in agent_results if r.get("status") == "completed" and r.get("output")]

    if len(completed_results) == 0:
        # All agents failed
        final_output = {
            "bm": "Maaf, sistem tidak dapat memproses permintaan anda sekarang. Sila cuba lagi.",
            "zh": "抱歉，系统目前无法处理您的请求。请稍后再试。",
        }.get(language, "Sorry, the system was unable to process your request. Please try again.")
    elif len(completed_results) == 1:
        # Single result — pass through directly (no synthesis overhead)
        final_output = completed_results[0].get("output", "")
    else:
        # Multiple results — synthesize into coherent answer
        final_output = await _synthesize_multi_agent(query, language, completed_results)

    log.info(
        "merger_done",
        agents_used=agents_used,
        citations=len(merged_citations),
        confidence=overall_confidence,
        total_latency_ms=round(total_latency, 1),
        output_flagged=output_flagged,
        synthesis="multi" if len(completed_results) > 1 else "passthrough",
    )

    return {
        "final_output": final_output,
        "merged_citations": merged_citations,
        "overall_confidence": overall_confidence,
        "suggestions": suggestions,
        "agents_used": agents_used,
        "total_latency_ms": round(total_latency, 1),
        "output_flagged": output_flagged,
    }
