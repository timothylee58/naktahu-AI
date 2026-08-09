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
    # None means "couldn't confidently classify" — hybrid_search treats a
    # None domain_filter as search-everything, which is the correct
    # fallback. A string default here is a trap: "government" looks like
    # a safe default but is itself a domain, and if it happens to be
    # empty of content (as it has been), every misclassified query
    # silently retrieves nothing instead of falling back to full-corpus
    # search — see CLAUDE.md Trap #6.
    domain: Optional[str]
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
    # Structured per-chunk staleness records (chunk_id, source_title,
    # effective_date, days_since_effective) for chunks whose effective_date has
    # passed by more than the staleness window.
    stale_warnings: list[dict[str, Any]]
    # Set when the query asks about the user's own case-specific record
    # (e.g. "what's my EPF balance") rather than a general rules question —
    # NakTahu has no access to any user's records, so this carries the real
    # agency contact to show instead of attempting an answer.
    agency_contact: Optional[dict[str, str]]
    # Warung Watch — set by router_node when the query is asking about a
    # named place's live crowd status ("Is Pelita packed right now?")
    # rather than a knowledge-base question. When true, graph.py routes
    # straight to warung_watch_node instead of rag/analyst/synthesiser —
    # this is live, ephemeral crowd data, not something the RAG pipeline's
    # confidence-gated document citations model applies to.
    is_live_status_query: bool
    place_name: Optional[str]
