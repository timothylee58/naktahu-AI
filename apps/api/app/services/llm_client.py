"""LLM provider abstraction.

ILMU (OpenAI-compatible) is the primary provider for both chat and embeddings.
Anthropic claude-sonnet-4-20250514 is the fallback for the synthesiser only.
"""
from __future__ import annotations

import json
import os

import anthropic
from openai import AsyncOpenAI

# ILMU client — OpenAI SDK pointed at ILMU base URL
ilmu_client = AsyncOpenAI(
    api_key=os.environ.get("ILMU_API_KEY", "placeholder"),
    base_url=os.environ.get("ILMU_BASE_URL", "https://api.ilmu.gov.my/v1"),
)

# Anthropic client — fallback for synthesiser when ILMU fails or confidence < 0.6
anthropic_client = anthropic.AsyncAnthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", "placeholder"),
)

# OpenAI client. NOT an embedding fallback for the live RAG corpus — see the
# warning on OPENAI_EMBEDDING_MODEL below before wiring this into any query or
# ingestion path.
_openai_key = os.environ.get("OPENAI_API_KEY", "")
openai_client: AsyncOpenAI | None = AsyncOpenAI(api_key=_openai_key) if _openai_key else None

ILMU_CHAT_MODEL: str = os.environ.get("ILMU_CHAT_MODEL", "ilmu-chat")
ILMU_EMBEDDING_MODEL: str = os.environ.get("ILMU_EMBEDDING_MODEL", "ilmu-embedding")

# The embedding model is a property of the CORPUS, never a per-request choice.
#
# document_chunks.embedding is vector(1536), written by ILMU_EMBEDDING_MODEL.
# text-embedding-3-small is *also* 1536-dimensional, so substituting it does not
# raise — pgvector happily computes a cosine distance between two vectors from
# completely different embedding spaces and returns a number that means nothing.
# hybrid_search weights cosine 0.7 / BM25 0.3, so the BM25 half keeps producing
# plausible-looking results while the semantic half is noise, and analyst_node
# then scores, ranks and cites those chunks with a confidence derived partly
# from that noise. Nothing anywhere logs an error.
#
# Worse on the write side: scripts/ingest_feed.py embeds straight into
# document_chunks, so a provider swap mid-ingest writes OpenAI-space rows
# permanently alongside ILMU-space ones, with no way to tell them apart
# afterwards.
#
# Switching embedding providers is therefore a corpus migration — re-embed
# every row — not a runtime fallback. This constant exists only for
# scripts/ingest.py, which builds the separate dosm_documents table (not read
# by live RAG; see CLAUDE.md Trap #14).
OPENAI_EMBEDDING_MODEL: str = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
FALLBACK_MODEL: str = "claude-sonnet-4-20250514"


def extract_json_object(raw: str) -> dict:
    """Extract the first well-formed JSON object from a raw LLM completion.

    Robust to markdown code fences and trailing commentary after the JSON
    (e.g. '{...} Let me know if you need anything else!') — a naive greedy
    regex like r'\\{.*\\}' matches from the first '{' to the LAST '}' in the
    whole completion, so it corrupts parsing the moment the model appends
    any text containing a brace, silently discarding an otherwise-correct
    classification. Uses JSONDecoder.raw_decode to parse only the first
    balanced object starting at the first '{', ignoring everything after it
    — no dependence on where (or whether) a matching closing brace appears
    later in unrelated trailing text.
    """
    start = raw.find("{")
    if start == -1:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    except (ValueError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}
