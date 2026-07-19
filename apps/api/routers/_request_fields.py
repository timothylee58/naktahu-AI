"""Shared bounded-field types for request metadata (language/domain) that
several routers accept alongside a query. Centralised so the valid set
can't drift between routers the way document_chunks.valid_domain and the
router/guard `_VALID_DOMAINS` sets have drifted before (CLAUDE.md Trap #6).

`domain` here intentionally allows "general" in addition to the 10
canonical RAG domains — feedback/history/share entries aren't always tied
to a specific retrieval domain, and "general" is the existing app-wide
sentinel default for that case (see ShareRequest.domain).
"""
from __future__ import annotations

from typing import Literal

Language = Literal["bm", "en", "ms", "zh"]
Domain = Literal[
    "government", "education", "legal", "finance", "healthcare",
    "epf", "tax", "business", "immigration", "culture", "general",
]
