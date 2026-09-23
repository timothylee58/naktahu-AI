"""Embedding-text construction for madani_scheme rows.

No ingestion pipeline writes to madani_scheme yet (it's still empty as of
migration 037 — no independently-verified scheme content exists). This
module is the piece a future scraper/data-entry tool will need once real
rows exist: build_scheme_embedding_text() is the exact concatenation
convention hybrid_search_madani_schemes() (migration 038) is tuned
against, and embed_scheme() is the thin wrapper that actually calls an
embedding model. Kept separate from app/services/vector_store.py to avoid
a circular import — vector_store.py is imported BY app/agents/rag_node.py,
so importing rag_node's _embed back into vector_store.py would be
circular; this module imports it instead, lazily, matching the
lazy-import pattern already used elsewhere (e.g. guard_node.py) for the
same reason.
"""
from __future__ import annotations

from typing import Any


def build_scheme_embedding_text(scheme: dict[str, Any]) -> str:
    """title + description + category + scope, not description alone, so
    semantic search picks up category/scope context ("Selangor",
    "pendidikan") even when a query doesn't use the scheme's exact
    wording. Field order matters a little for BM25-style term weighting
    (earlier terms in a concatenated blob are marginally favoured by
    ts_rank_cd's default normalization) — name first since that's what a
    scheme is most often referred to by.
    """
    parts = [
        scheme.get("scheme_name", ""),
        scheme.get("description", ""),
        scheme.get("category", ""),
        scheme.get("scope", ""),
    ]
    return " ".join(p for p in parts if p)


async def embed_scheme(scheme: dict[str, Any]) -> list[float]:
    """Embed one scheme row's rendered text via the same ILMU->OpenAI
    fallback every other embedding call in this codebase uses.
    """
    from app.agents.rag_node import _embed

    text = build_scheme_embedding_text(scheme)
    return await _embed(text)
