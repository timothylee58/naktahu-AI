"""grant_programmes lookup — structured facts to back grant-finder's answers.

Joins to RAG findings by source_url at query time (see migration
019_grant_programmes.sql for why this isn't a document_chunks column/FK).
Degrades gracefully: an empty table or a lookup miss just means no
structured facts are available yet for that URL — callers fall back to
their existing behavior, never fabricate a value.
"""
from __future__ import annotations

import os
from typing import Any

from supabase import acreate_client


async def get_grant_programmes_by_urls(urls: list[str]) -> dict[str, dict[str, Any]]:
    """Return {source_url: programme_row} for any of the given URLs that have
    a structured grant_programmes record. Missing/empty input -> empty dict."""
    unique_urls = [u for u in dict.fromkeys(urls) if u]
    if not unique_urls:
        return {}

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return {}

    client = await acreate_client(url, key)
    res = (
        await client.table("grant_programmes")
        .select("*")
        .in_("source_url", unique_urls)
        .execute()
    )
    return {row["source_url"]: row for row in (res.data or [])}
