"""LangGraph StateGraph definition for the NakTahu AI pipeline.

Execution order:
  START → router → guard → rag → analyst → synthesiser   (normal path)
                       ↓     ↓
              warung_watch,  END  (blocked query — refusal already streamed)
              parliament_query
                       ↓
                      END  (live "is X packed right now" query, or a structured
                            Parliament bill/MP lookup — answered directly)

analyst → synthesiser also covers low confidence as long as SOME material was
retrieved: synthesiser hedges the answer and asks a targeted follow-up instead
of refusing outright (see synthesiser_node._partial_confidence_instruction).
analyst → clarification is the narrower case — needs_clarification=True AND
retrieved_chunks is empty, i.e. there is nothing at all to answer from.

warung_watch and parliament_query both branch off AFTER guard, not directly
off router — every query, including these short-circuit ones, still passes
guard_node's harmful-intent keyword check (and optional LLM check) first.
place_name/parliament_bill_number/parliament_mp_query are LLM-extracted
free text that gets echoed straight back into the answer, so skipping guard
entirely for these paths would have meant a crafted query classified as
live-status or structured-parliament could bypass moderation. Once past
guard, each is a short-circuit that bypasses rag/analyst/synthesiser:
warung_watch answers from live crowdsourced check-in data (its own
freshness/report-count framing instead of a confidence-gated citation),
and parliament_query answers from a direct relational read over
mp_profiles/mp_votes/parliament_bills (FK-linked since migration 025 — the
Postgres property graph this domain needs), which a chunk-retrieval RAG
pass answers worse than a plain SQL join would. General Hansard
debate-content questions still take the normal RAG path unaffected.

Pass a PostgresSaver (or other checkpointer) to build_graph() for persistent
multi-turn state. Default export is stateless for the SSE /query endpoint.
"""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.analyst_node import analyst_node
from app.agents.clarification import clarification_message
from app.agents.guard_node import guard_node
from app.agents.parliament_query_node import parliament_query_node
from app.agents.rag_node import rag_node
from app.agents.router_node import router_node
from app.agents.synthesiser_node import synthesiser_node
from app.agents.warung_watch_node import warung_watch_node
from app.models.state import AgentState


def _clarification_node(state: AgentState) -> dict:
    """Emit a clarification prompt when analyst confidence is too low."""
    return {"streaming_token_buffer": clarification_message(state.get("language"))}


def _route_after_guard(state: AgentState) -> str:
    """Blocked queries end immediately (refusal already streamed). Live
    business-status queries ("Is Pelita packed right now?") that passed
    guard's check route to warung_watch_node instead of rag. Structured
    Parliament lookups (a bill's vote record, a specific MP/constituency)
    route to parliament_query_node — a direct relational read, not a
    chunk-retrieval-shaped question. Everything else takes the normal RAG
    path, including general Hansard debate-content questions."""
    if state.get("error") == "blocked":
        return END
    if state.get("is_live_status_query") and state.get("place_name"):
        return "warung_watch"
    if state.get("is_structured_parliament_query") and (
        state.get("parliament_bill_number") or state.get("parliament_mp_query")
    ):
        return "parliament_query"
    return "rag"


def _route_after_analyst(state: AgentState) -> str:
    """Low confidence routes to the synthesiser (hedged answer + a targeted
    clarifying question) whenever there is still SOME retrieved material to
    answer from — only a query with literally nothing retrieved (e.g. too
    vague/off-topic to search at all) falls through to the bare
    clarification-prompt node. See synthesiser_node._partial_confidence_instruction
    for what "hedged" means here; this split is what lets a low-confidence
    answer still share the general rule instead of refusing outright."""
    if state.get("needs_clarification", False) and not state.get("retrieved_chunks"):
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
    graph.add_node("parliament_query", parliament_query_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "guard")
    graph.add_edge("warung_watch", END)
    graph.add_edge("parliament_query", END)
    graph.add_conditional_edges(
        "guard",
        _route_after_guard,
        {"rag": "rag", "warung_watch": "warung_watch", "parliament_query": "parliament_query", END: END},
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
