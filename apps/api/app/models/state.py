"""AgentState TypedDict and Citation model for the LangGraph pipeline."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from app.services.vector_store import ChunkResult


class Citation(TypedDict):
    title: str
    ministry: str
    url: str
    confidence: float


class AgentState(TypedDict, total=False):
    query: str
    language: Literal["bm", "en"]
    domain: str
    session_id: str
    user_id: Optional[str]
    retrieved_chunks: list[ChunkResult]
    citations: list[Citation]
    confidence_score: float
    needs_clarification: bool
    streaming_token_buffer: str
    error: Optional[str]
