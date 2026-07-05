"""LangGraph StateGraph definition for the NakTahu AI pipeline.

Execution order:
  START → router → guard → rag → analyst → synthesiser   (normal path)
                        ↓                → clarification  (needs_clarification=True)
                       END  (blocked query — refusal already streamed)

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
    """Skip the pipeline if guard_node already emitted a refusal."""
    if state.get("error") == "blocked":
        return END
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

    graph.add_edge(START, "router")
    graph.add_edge("router", "guard")
    graph.add_conditional_edges(
        "guard",
        _route_after_guard,
        {"rag": "rag", END: END},
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
