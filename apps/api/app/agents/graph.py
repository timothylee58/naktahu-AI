"""LangGraph StateGraph definition for the NakTahu AI pipeline.

Execution order:
  START → router → guard → rag → analyst → synthesiser   (normal path)
                       ↓     ↓                → clarification  (needs_clarification=True)
              warung_watch  END  (blocked query — refusal already streamed)
                       ↓
                      END  (live "is X packed right now" query — answered directly)

warung_watch branches off AFTER guard, not directly off router — every
query, including live-status ones, still passes guard_node's harmful-intent
keyword check (and optional LLM check) first. place_name is LLM-extracted
free text that gets echoed straight back into the answer, so skipping guard
entirely for this path would have meant a crafted query classified as
live-status could bypass moderation. Once past guard, warung_watch is a
short-circuit that bypasses rag/analyst/synthesiser, since it answers from
live crowdsourced check-in data, not the RAG corpus, and that data has its
own freshness/report-count framing instead of a confidence-gated citation.

Pass a PostgresSaver (or other checkpointer) to build_graph() for persistent
multi-turn state. Default export is stateless for the SSE /query endpoint.
"""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.analyst_node import analyst_node
from app.agents.guard_node import guard_node
from app.agents.rag_node import rag_node
from app.agents.router_node import router_node
from app.agents.synthesiser_node import synthesiser_node
from app.agents.warung_watch_node import warung_watch_node
from app.models.state import AgentState


def _clarification_node(state: AgentState) -> dict:
    """Emit a clarification prompt when analyst confidence is too low."""
    lang = state.get("language", "en")
    if lang == "bm":
        msg = (
            "Maaf, saya tidak pasti dengan jawapan untuk soalan anda. "
            "Boleh anda berikan lebih maklumat atau nyatakan soalan dengan lebih jelas?"
        )
    else:
        msg = (
            "I'm not confident enough to answer this question accurately. "
            "Could you please provide more context or rephrase your question?"
        )
    return {"streaming_token_buffer": msg}


def _route_after_guard(state: AgentState) -> str:
    """Blocked queries end immediately (refusal already streamed). Live
    business-status queries ("Is Pelita packed right now?") that passed
    guard's check route to warung_watch_node instead of rag — everything
    else takes the normal RAG path."""
    if state.get("error") == "blocked":
        return END
    if state.get("is_live_status_query") and state.get("place_name"):
        return "warung_watch"
    return "rag"


def _route_after_analyst(state: AgentState) -> str:
    if state.get("needs_clarification", False):
        return "clarification"
    return "synthesiser"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("guard", guard_node)
    graph.add_node("rag", rag_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("synthesiser", synthesiser_node)
    graph.add_node("clarification", _clarification_node)
    graph.add_node("warung_watch", warung_watch_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "guard")
    graph.add_edge("warung_watch", END)
    graph.add_conditional_edges(
        "guard",
        _route_after_guard,
        {"rag": "rag", "warung_watch": "warung_watch", END: END},
    )
    graph.add_edge("rag", "analyst")
    graph.add_conditional_edges(
        "analyst",
        _route_after_analyst,
        {"synthesiser": "synthesiser", "clarification": "clarification"},
    )
    graph.add_edge("synthesiser", END)
    graph.add_edge("clarification", END)

    return graph


def compile_pipeline(checkpointer: Optional[Any] = None):
    """Compile the main Q&A pipeline, optionally with a PostgresSaver."""
    return build_graph().compile(checkpointer=checkpointer)


# Stateless graph for the SSE /query endpoint (default).
pipeline = compile_pipeline(checkpointer=None)
