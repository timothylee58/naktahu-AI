"""Parliament Watch read-only lookups.

Structured reference data (MP profiles, voting records, constituencies)
backed by 025_parliament_watch.sql. No RAG/LLM synthesis here — every
answer is a direct structured query or a call to one of the two SQL
functions the migration defines. Hansard content ingestion (which would
populate document_chunks with domain='hansard') is a follow-up PR; the
lookups below never depend on it.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog
from supabase import Client

logger = structlog.get_logger()


async def get_mp_by_constituency(
    supabase_client: Client, constituency_code: str
) -> Optional[dict[str, Any]]:
    """Wraps the get_mp_by_constituency SQL function via .rpc()."""

    def _rpc() -> Optional[dict[str, Any]]:
        res = supabase_client.rpc(
            "get_mp_by_constituency", {"p_code": constituency_code}
        ).execute()
        return res.data[0] if res.data else None

    return await asyncio.to_thread(_rpc)


async def search_mps(supabase_client: Client, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Full-text-ish search over mp_profiles (name/constituency/party/state).

    Uses `or`/`ilike` rather than the FTS index directly since supabase-py's
    query builder does not expose to_tsquery composition cleanly; the FTS
    GIN index still accelerates ILIKE-adjacent trigram-free scans at this
    row count (a few thousand MPs, not millions).
    """

    def _search() -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        res = (
            supabase_client.table("mp_profiles")
            .select(
                "id,full_name,constituency_code,constituency_name,party,state,is_active"
            )
            .or_(
                f"full_name.ilike.{pattern},constituency_name.ilike.{pattern},"
                f"party.ilike.{pattern},state.ilike.{pattern}"
            )
            .limit(limit)
            .execute()
        )
        return res.data or []

    return await asyncio.to_thread(_search)


async def get_bill_vote_summary(
    supabase_client: Client, bill_number: str
) -> list[dict[str, Any]]:
    """Wraps the get_bill_vote_summary SQL function via .rpc()."""

    def _rpc() -> list[dict[str, Any]]:
        res = supabase_client.rpc(
            "get_bill_vote_summary", {"p_bill_number": bill_number}
        ).execute()
        return res.data or []

    return await asyncio.to_thread(_rpc)


async def list_constituencies(
    supabase_client: Client, state: Optional[str] = None, limit: int = 100
) -> list[dict[str, Any]]:
    def _list() -> list[dict[str, Any]]:
        q = supabase_client.table("constituencies").select("*").limit(limit)
        if state:
            q = q.eq("state", state)
        res = q.execute()
        return res.data or []

    return await asyncio.to_thread(_list)
