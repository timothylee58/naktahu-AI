"""LangGraph StateGraph definition for the NakTahu AI pipeline.

Execution order:
  START → router → rag → analyst → synthesiser   (normal path)
                                 → clarification  (needs_clarification=True)

Compile with checkpointer=None (stateless).
The SSE endpoint uses astream(stream_mode="custom") to receive tokens written
by synthesiser_node via get_stream_writer().
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.analyst_node import analyst_node
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


def _route_after_analyst(state: AgentState) -> str:
    if state.get("needs_clarification", False):
        return "clarification"
    return "synthesiser"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("rag", rag_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("synthesiser", synthesiser_node)
    graph.add_node("clarification", _clarification_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "rag")
    graph.add_edge("rag", "analyst")
    graph.add_conditional_edges(
        "analyst",
        _route_after_analyst,
        {"synthesiser": "synthesiser", "clarification": "clarification"},
    )
    graph.add_edge("synthesiser", END)
    graph.add_edge("clarification", END)

    return graph


# Compiled stateless graph — import this in the endpoint
pipeline = build_graph().compile(checkpointer=None)
