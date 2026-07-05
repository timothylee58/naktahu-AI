"""Study Agent state."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class StudyAgentState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    subject: str
    paper_text: str
    document_base64: str
    message: str
    questions: list[str]
    explanations: list[dict[str, Any]]
    topic_progress: dict[str, int]
    active_question_index: int
    turns_count: int
    status: str
    tool_calls: list[dict[str, Any]]
