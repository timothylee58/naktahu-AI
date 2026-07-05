"""Study Agent LangGraph — SPM past-paper upload + education RAG."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.study_agent.nodes import explain_node, extract_questions_node, intake_node, track_topics_node
from app.agents.study_agent.state import StudyAgentState

_compiled: Any = None


def build_study_agent_graph() -> StateGraph:
    graph = StateGraph(StudyAgentState)
    graph.add_node("intake", intake_node)
    graph.add_node("extract_questions", extract_questions_node)
    graph.add_node("explain", explain_node)
    graph.add_node("track_topics", track_topics_node)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "extract_questions")
    graph.add_edge("extract_questions", "explain")
    graph.add_edge("explain", "track_topics")
    graph.add_edge("track_topics", END)
    return graph


def get_study_agent_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_study_agent_graph().compile(checkpointer=cp)
    return _compiled
