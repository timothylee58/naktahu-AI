"""Answer feedback: thumbs up/down persisted to Supabase.

Negative-rated rows are the primary long-term consumer — they're candidate
additions to apps/api/evals/ once a human reviews them, giving the eval
harness a growing, real-usage-derived dataset instead of only hand-written
cases.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog
from supabase import Client

logger = structlog.get_logger()

MAX_RESPONSE_SUMMARY = 2000


async def submit_feedback(
    *,
    supabase_client: Client,
    user_id: Optional[str],
    session_id: str,
    query: str,
    response_text: str,
    citations: list[Any],
    domain: str,
    language: str,
    rating: int,
) -> None:
    row = {
        "user_id": user_id,
        "session_id": session_id,
        "query": query,
        "response_summary": response_text[:MAX_RESPONSE_SUMMARY],
        "citations": citations,
        "domain": domain,
        "language": language,
        "rating": rating,
    }

    def _insert() -> None:
        supabase_client.table("feedback").insert(row).execute()

    await asyncio.to_thread(_insert)
    logger.info(
        "feedback_submitted",
        user_id=user_id,
        domain=domain,
        language=language,
        rating=rating,
    )
