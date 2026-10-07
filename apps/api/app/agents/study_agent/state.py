"""Study Agent state."""
from __future__ import annotations

from typing import Any, TypedDict


class StudyAgentState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    level: str  # "spm" | "stpm" | "a-level"
    subject: str
    mode: str  # "explain" | "quiz"
    paper_text: str
    document_base64: str
    image_base64: str
    image_mime_type: str
    message: str
    questions: list[str]
    explanations: list[dict[str, Any]]
    quiz: list[dict[str, Any]]
    quiz_score: int
    quiz_answered: int
    topic_progress: dict[str, int]
    active_question_index: int
    turns_count: int
    status: str
    tool_calls: list[dict[str, Any]]
