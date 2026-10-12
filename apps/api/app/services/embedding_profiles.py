"""Embedding profiles: which model embeds the corpus, and where the vectors live.

A profile ties together four things that must never be mixed independently:
the model, its output dimension, the document_chunks/madani_scheme column that
holds its vectors, and the search RPC that reads that column. Vectors from
different models are not comparable even when the dimensions match, so a query
embedded under one profile may only be searched against that profile's column.

``openai``       text-embedding-3-small, 1536-dim, column ``embedding``,
                 RPC ``hybrid_search`` (the original corpus).
``ilmu_bge_m3``  ILMU-hosted bge-m3, 1024-dim, column ``embedding_v2``,
                 RPC ``hybrid_search_v2`` (migration 056).

EMBEDDING_PROFILE picks the READ profile (queries + which RPC). Writers use
EMBEDDING_WRITE_PROFILES (comma-separated) so ingestion can fill both columns
during the transition and the read profile can be flipped back without losing
rows ingested in the meantime. Both default to ``openai``, i.e. nothing changes
until the env vars are set.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingProfile:
    name: str
    dims: int
    column: str
    chunks_rpc: str
    madani_rpc: str
    ilmu_model: str


PROFILES: dict[str, EmbeddingProfile] = {
    "openai": EmbeddingProfile(
        name="openai",
        dims=1536,
        column="embedding",
        chunks_rpc="hybrid_search",
        madani_rpc="hybrid_search_madani_schemes",
        ilmu_model="openai/text-embedding-3-small",
    ),
    "ilmu_bge_m3": EmbeddingProfile(
        name="ilmu_bge_m3",
        dims=1024,
        column="embedding_v2",
        chunks_rpc="hybrid_search_v2",
        madani_rpc="hybrid_search_madani_schemes_v2",
        ilmu_model="bge-m3",
    ),
}

DEFAULT_PROFILE = "openai"


def get_profile(name: str | None) -> EmbeddingProfile:
    key = (name or DEFAULT_PROFILE).strip().lower() or DEFAULT_PROFILE
    try:
        return PROFILES[key]
    except KeyError:
        # Fail at startup/first use rather than silently searching the wrong column.
        raise ValueError(f"Unknown EMBEDDING_PROFILE {key!r}; expected one of {sorted(PROFILES)}") from None


def active_profile() -> EmbeddingProfile:
    return get_profile(os.environ.get("EMBEDDING_PROFILE"))


def write_profiles() -> list[EmbeddingProfile]:
    raw = os.environ.get("EMBEDDING_WRITE_PROFILES", DEFAULT_PROFILE)
    names = [n.strip() for n in raw.split(",") if n.strip()] or [DEFAULT_PROFILE]
    seen: dict[str, EmbeddingProfile] = {}
    for n in names:
        p = get_profile(n)
        seen[p.name] = p
    return list(seen.values())
