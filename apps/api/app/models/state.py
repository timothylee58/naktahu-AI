"""AgentState TypedDict and Citation model for the LangGraph pipeline."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from app.services.vector_store import ChunkResult


class Citation(TypedDict):
    title: str
    ministry: str
    url: str
    confidence: float
    stale_disclaimer: bool  # True when expiry_aware chunk is >90 days old


class AgentState(TypedDict, total=False):
    query: str
    language: Literal["bm", "en", "zh"]
    domain: str
    intent: str
    session_id: str
    user_id: Optional[str]
    retrieved_chunks: list[ChunkResult]
    citations: list[Citation]
    confidence_score: float
    needs_clarification: bool
    streaming_token_buffer: str
    error: Optional[str]
    output_flagged: bool
    skip_history_persist: bool
    suggestions: list[str]
    # Freshness signals. faithfulness/confidence only measure answer-to-chunk
    # consistency, not whether the chunk is still current — these carry the
    # recency verdict from analyst_node to synthesiser_node so a stale-but-
    # faithful answer is date-stamped and hedged rather than stated as current.
    stale_warning: bool
    answer_as_of: Optional[str]
