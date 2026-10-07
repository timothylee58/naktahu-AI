"""Cross-encoder-style re-ranking pass over hybrid_search's candidate pool.

hybrid_search() (vector_store.py) already combines cosine similarity (0.7)
and BM25 rank (0.3) — that IS "hybrid search". What's missing, and what this
module adds, is a second pass that looks at (query, chunk) pairs *together*
rather than scoring each independently, which is where dense+BM25 both miss
niche legal/regulatory phrasing (the exact case the roadmap ask named).

No local ML inference infra exists in this deployment (no GPU, no
sentence-transformers dependency, Railway container sizing untested for it),
and a hosted third-party reranking API would be a new external dependency
and a new secret. Per CLAUDE.md's "ILMU primary" provider rule and "no new
LLM provider without an explicit architecture decision", this re-purposes
the existing ILMU chat client as a listwise reranker instead — one more
network hop, but no new provider, no new infra, no new secret.

Feature-flagged OFF by default (RERANK_ENABLED unset/false) — flipping the
retrieval order for every query is a real behaviour change that needs an
eval-set comparison (evals/answer_quality.jsonl, language_accuracy.jsonl)
before it's the default, not something this change should silently turn on.
"""
from __future__ import annotations

import os

import structlog

from app.services.llm_client import ILMU_CHAT_MODEL, extract_json_object, ilmu_client
from app.services.vector_store import ChunkResult

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a search-result re-ranker for a Malaysian government knowledge base. "
    "You will be given a user query and a numbered list of candidate document excerpts. "
    "Return JSON with a single key 'ranked_ids': an array of the excerpt numbers, "
    "most relevant to the query first. Include EVERY number exactly once. "
    "Judge relevance by whether the excerpt would let someone answer the query correctly — "
    "not by keyword overlap alone."
)

_MAX_CONTENT_CHARS = 400


def rerank_enabled() -> bool:
    return os.environ.get("RERANK_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _build_candidate_list(chunks: list[ChunkResult]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        snippet = c.content[:_MAX_CONTENT_CHARS]
        lines.append(f"[{i}] ({c.ministry}) {snippet}")
    return "\n\n".join(lines)


async def rerank_chunks(*, query: str, chunks: list[ChunkResult], top_n: int) -> list[ChunkResult]:
    """Re-order `chunks` by relevance to `query`, returning the top `top_n`.

    Degrades to the original hybrid_search order (chunks[:top_n]) on any
    failure — malformed model output, an unparseable index, a timeout — so
    a reranker outage never breaks retrieval, matching how rag_node's own
    hybrid_search failure already degrades to an empty-chunks result rather
    than propagating.
    """
    if len(chunks) <= 1:
        return chunks[:top_n]

    fallback = chunks[:top_n]
    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Query: {query}\n\nCandidates:\n{_build_candidate_list(chunks)}"},
            ],
            max_tokens=256,
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        parsed = extract_json_object(raw)
        ranked_ids = parsed.get("ranked_ids")
        if not isinstance(ranked_ids, list) or not ranked_ids:
            raise ValueError("reranker returned no ranked_ids")

        seen: set[int] = set()
        ordered: list[ChunkResult] = []
        for raw_idx in ranked_ids:
            idx = int(raw_idx) - 1  # candidates are 1-indexed in the prompt
            if 0 <= idx < len(chunks) and idx not in seen:
                seen.add(idx)
                ordered.append(chunks[idx])
        # Any chunk the model omitted or mis-indexed still gets appended
        # (in original order) rather than silently dropped — a partial
        # ranking is still better than losing a candidate entirely.
        for i, c in enumerate(chunks):
            if i not in seen:
                ordered.append(c)

        return ordered[:top_n]
    except Exception as exc:
        log.warning("rerank_failed", error=str(exc), query_len=len(query))
        return fallback
