"""Product feedback (bugs / feature requests / general) — backs the profile
page's "Give Feedback" card, migration 047_product_feedback.sql.

Deliberately separate from services/feedback.py, which is the per-answer
thumbs-up/down rating that feeds the eval-harness mining pipeline — see
that migration's own docstring for why this needed its own table.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from supabase import Client


async def create_product_feedback(
    supabase_client: Client,
    *,
    user_id: str,
    category: str,
    title: str,
    description: str,
    page_context: Optional[str],
) -> dict[str, Any]:
    def _insert() -> dict[str, Any]:
        res = (
            supabase_client.table("product_feedback")
            .insert(
                {
                    "user_id": user_id,
                    "category": category,
                    "title": title,
                    "description": description,
                    "page_context": page_context,
                }
            )
            .execute()
        )
        return res.data[0] if res.data else {}

    return await asyncio.to_thread(_insert)


async def list_own_product_feedback(
    supabase_client: Client, *, user_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    def _list() -> list[dict[str, Any]]:
        res = (
            supabase_client.table("product_feedback")
            .select("id,category,title,description,status,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    return await asyncio.to_thread(_list)
