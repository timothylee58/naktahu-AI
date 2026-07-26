"""Eligibility Agent LangGraph — multi-turn intake -> grant RAG -> analyst scoring.

Compiled WITH a checkpointer (unlike the single-shot sme_compliance_navigator
graph) because intake spans multiple turns before the graph completes —
mirrors the now-deleted grant_finder checkpointer pattern.

synthesiser_node is a streaming async generator, not a graph node — it's
invoked directly by app/routers/eligibility.py once intake_complete is True,
the same way grant_finder's match_node used to run inline in a single pass.
"""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.eligibility_agent.analyst_node import analyst_node
from app.agents.eligibility_agent.grant_rag_node import grant_rag_node
from app.agents.eligibility_agent.intake_node import intake_node
from app.agents.eligibility_agent.state import EligibilityState

_compiled: Any = None


async def _grant_rag_node(state: EligibilityState) -> dict[str, Any]:
    return await grant_rag_node(state, state.get("_supabase"))


def _route_after_intake(state: EligibilityState) -> str:
    return "grant_rag" if state.get("intake_complete") else END


def build_eligibility_agent_graph() -> StateGraph:
    graph = StateGraph(EligibilityState)
    graph.add_node("intake", intake_node)
    graph.add_node("grant_rag", _grant_rag_node)
    graph.add_node("analyst", analyst_node)
    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", _route_after_intake, {"grant_rag": "grant_rag", END: END})
    graph.add_edge("grant_rag", "analyst")
    graph.add_edge("analyst", END)
    return graph


def get_eligibility_agent_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_eligibility_agent_graph().compile(checkpointer=cp)
    return _compiled
