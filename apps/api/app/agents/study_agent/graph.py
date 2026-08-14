"""Study Agent LangGraph — SPM/STPM/A-Level past-paper upload (text, PDF, or
photo OCR) + education RAG, in either explain mode or quiz mode."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.study_agent.nodes import (
    explain_node,
    extract_questions_node,
    generate_quiz_node,
    intake_node,
    track_topics_node,
)
from app.agents.study_agent.state import StudyAgentState

_compiled: Any = None


def _route_by_mode(state: StudyAgentState) -> str:
    return "generate_quiz" if state.get("mode") == "quiz" else "explain"


def build_study_agent_graph() -> StateGraph:
    graph = StateGraph(StudyAgentState)
    graph.add_node("intake", intake_node)
    graph.add_node("extract_questions", extract_questions_node)
    graph.add_node("explain", explain_node)
    graph.add_node("generate_quiz", generate_quiz_node)
    graph.add_node("track_topics", track_topics_node)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "extract_questions")
    graph.add_conditional_edges(
        "extract_questions",
        _route_by_mode,
        {"explain": "explain", "generate_quiz": "generate_quiz"},
    )
    graph.add_edge("explain", "track_topics")
    graph.add_edge("generate_quiz", "track_topics")
    graph.add_edge("track_topics", END)
    return graph


def get_study_agent_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_study_agent_graph().compile(checkpointer=cp)
    return _compiled
