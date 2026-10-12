"""Embedding profiles: the read profile, the write profiles and their wiring.

Vectors from different models are not comparable, so every place that embeds or
searches must pick the column/RPC that belongs to the model it used.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding_profiles import PROFILES, active_profile, get_profile, write_profiles

_BGE = [0.2] * 1024
_OPENAI = [0.1] * 1536


def _resp(embedding: list[float]) -> MagicMock:
    item = MagicMock()
    item.embedding = embedding
    resp = MagicMock()
    resp.data = [item]
    return resp


def test_defaults_are_the_original_openai_profile(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_PROFILE", raising=False)
    monkeypatch.delenv("EMBEDDING_WRITE_PROFILES", raising=False)
    assert active_profile().name == "openai"
    assert [p.name for p in write_profiles()] == ["openai"]
    assert active_profile().column == "embedding"
    assert active_profile().chunks_rpc == "hybrid_search"


def test_env_selects_profiles_and_dedupes_write_list(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROFILE", " ILMU_BGE_M3 ")
    monkeypatch.setenv("EMBEDDING_WRITE_PROFILES", "openai, ilmu_bge_m3,openai")
    assert active_profile().name == "ilmu_bge_m3"
    assert [p.name for p in write_profiles()] == ["openai", "ilmu_bge_m3"]


def test_blank_env_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROFILE", "  ")
    monkeypatch.setenv("EMBEDDING_WRITE_PROFILES", " , ")
    assert active_profile().name == "openai"
    assert [p.name for p in write_profiles()] == ["openai"]


def test_unknown_profile_fails_loudly(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROFILE", "bge-m4")
    with pytest.raises(ValueError, match="Unknown EMBEDDING_PROFILE"):
        active_profile()


def test_profiles_have_distinct_columns_and_rpcs() -> None:
    cols = [p.column for p in PROFILES.values()]
    rpcs = [p.chunks_rpc for p in PROFILES.values()]
    assert len(set(cols)) == len(cols) and len(set(rpcs)) == len(rpcs)
    assert get_profile("ilmu_bge_m3").dims == 1024


# ── rag_node: query embedding follows the active profile ──────────────────

@pytest.mark.asyncio
async def test_embed_uses_bge_m3_on_ilmu_when_profile_selected(monkeypatch) -> None:
    from app.agents.rag_node import _embed

    monkeypatch.setenv("EMBEDDING_PROFILE", "ilmu_bge_m3")
    ilmu, oa = MagicMock(), MagicMock()
    ilmu.embeddings.create = AsyncMock(return_value=_resp(_BGE))
    oa.embeddings.create = AsyncMock()
    with patch("app.agents.rag_node.ilmu_client", ilmu), patch("app.agents.rag_node.openai_client", oa):
        assert await _embed("cukai") == _BGE
    assert ilmu.embeddings.create.await_args.kwargs["model"] == "bge-m3"
    oa.embeddings.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_bge_m3_failure_never_falls_back_to_openai(monkeypatch) -> None:
    """OpenAI vectors are a different space from the embedding_v2 column; a
    fallback would return plausible-looking nonsense instead of an error."""
    from app.agents.rag_node import _embed

    monkeypatch.setenv("EMBEDDING_PROFILE", "ilmu_bge_m3")
    ilmu, oa = MagicMock(), MagicMock()
    ilmu.embeddings.create = AsyncMock(side_effect=RuntimeError("ILMU down"))
    oa.embeddings.create = AsyncMock(return_value=_resp(_OPENAI))
    with patch("app.agents.rag_node.ilmu_client", ilmu), patch("app.agents.rag_node.openai_client", oa), \
            pytest.raises(RuntimeError, match="ILMU down"):
        await _embed("cukai")
    oa.embeddings.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_bge_m3_wrong_dimension_is_rejected(monkeypatch) -> None:
    from app.agents.rag_node import _embed

    monkeypatch.setenv("EMBEDDING_PROFILE", "ilmu_bge_m3")
    ilmu = MagicMock()
    ilmu.embeddings.create = AsyncMock(return_value=_resp([0.1] * 4096))
    with patch("app.agents.rag_node.ilmu_client", ilmu), pytest.raises(ValueError, match="4096 dims, expected 1024"):
        await _embed("cukai")


@pytest.mark.asyncio
async def test_default_profile_embed_path_is_unchanged(monkeypatch) -> None:
    from app.agents.rag_node import _embed

    monkeypatch.delenv("EMBEDDING_PROFILE", raising=False)
    ilmu, oa = MagicMock(), MagicMock()
    ilmu.embeddings.create = AsyncMock(side_effect=RuntimeError("404"))
    oa.embeddings.create = AsyncMock(return_value=_resp(_OPENAI))
    with patch("app.agents.rag_node.ilmu_client", ilmu), patch("app.agents.rag_node.openai_client", oa):
        assert await _embed("cukai") == _OPENAI
    assert oa.embeddings.create.await_args.kwargs["model"] == "text-embedding-3-small"


# ── rag_node: storage vectors follow the write profiles ───────────────────

@pytest.mark.asyncio
async def test_embed_for_storage_defaults_to_the_original_column(monkeypatch) -> None:
    from app.agents.rag_node import embed_for_storage

    monkeypatch.delenv("EMBEDDING_WRITE_PROFILES", raising=False)
    oa = MagicMock()
    oa.embeddings.create = AsyncMock(return_value=_resp(_OPENAI))
    with patch("app.agents.rag_node.ilmu_client", MagicMock()), patch("app.agents.rag_node.openai_client", oa), \
            patch("app.agents.rag_node.ILMU_EMBEDDING_MODEL", ""):
        assert await embed_for_storage("teks") == {"embedding": _OPENAI}


@pytest.mark.asyncio
async def test_embed_for_storage_fills_every_write_profile(monkeypatch) -> None:
    from app.agents.rag_node import embed_for_storage

    monkeypatch.setenv("EMBEDDING_WRITE_PROFILES", "openai,ilmu_bge_m3")
    ilmu, oa = MagicMock(), MagicMock()
    ilmu.embeddings.create = AsyncMock(return_value=_resp(_BGE))
    oa.embeddings.create = AsyncMock(return_value=_resp(_OPENAI))
    with patch("app.agents.rag_node.ilmu_client", ilmu), patch("app.agents.rag_node.openai_client", oa), \
            patch("app.agents.rag_node.ILMU_EMBEDDING_MODEL", ""):
        vectors = await embed_for_storage("teks")
    assert vectors == {"embedding": _OPENAI, "embedding_v2": _BGE}


@pytest.mark.asyncio
async def test_embed_for_storage_raises_when_any_profile_fails(monkeypatch) -> None:
    """A row with one column filled and one silently empty would be invisible
    to the other read profile — the caller must count it as failed instead."""
    from app.agents.rag_node import embed_for_storage

    monkeypatch.setenv("EMBEDDING_WRITE_PROFILES", "openai,ilmu_bge_m3")
    ilmu, oa = MagicMock(), MagicMock()
    ilmu.embeddings.create = AsyncMock(side_effect=RuntimeError("ILMU down"))
    oa.embeddings.create = AsyncMock(return_value=_resp(_OPENAI))
    with patch("app.agents.rag_node.ilmu_client", ilmu), patch("app.agents.rag_node.openai_client", oa), \
            patch("app.agents.rag_node.ILMU_EMBEDDING_MODEL", ""), pytest.raises(RuntimeError, match="ILMU down"):
        await embed_for_storage("teks")


# ── vector_store: the RPC matches the profile ─────────────────────────────

def _rpc_client() -> MagicMock:
    client = MagicMock()
    client.rpc.return_value.execute = AsyncMock(return_value=MagicMock(data=[]))
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile,chunks_rpc,madani_rpc",
    [
        ("openai", "hybrid_search", "hybrid_search_madani_schemes"),
        ("ilmu_bge_m3", "hybrid_search_v2", "hybrid_search_madani_schemes_v2"),
    ],
)
async def test_vector_store_calls_the_rpc_for_the_active_profile(monkeypatch, profile, chunks_rpc, madani_rpc) -> None:
    from app.services import vector_store

    monkeypatch.setenv("EMBEDDING_PROFILE", profile)
    client = _rpc_client()
    with patch.object(vector_store, "_get_client", AsyncMock(return_value=client)):
        await vector_store.hybrid_search("cukai", [0.0], domain="tax")
        assert client.rpc.call_args.args[0] == chunks_rpc
        await vector_store.hybrid_search_madani_schemes("bantuan", [0.0])
        assert client.rpc.call_args.args[0] == madani_rpc


@pytest.mark.asyncio
async def test_v2_rpc_error_is_not_retried_with_the_v1_function(monkeypatch) -> None:
    """The keyword_query retry targets pre-051 hybrid_search only; for v2 it
    would just repeat the same failing call (or hit the wrong column)."""
    from app.services import vector_store

    monkeypatch.setenv("EMBEDDING_PROFILE", "ilmu_bge_m3")
    client = MagicMock()
    client.rpc.return_value.execute = AsyncMock(side_effect=RuntimeError("function hybrid_search_v2 does not exist"))
    with patch.object(vector_store, "_get_client", AsyncMock(return_value=client)), \
            pytest.raises(RuntimeError, match="hybrid_search_v2"):
        await vector_store.hybrid_search("memohon bantuan", [0.0], domain=None)
    assert client.rpc.call_count == 1


# ── ingest_feed: supersede neighbours use a vector with its own RPC ───────

def test_supersede_search_uses_the_active_profiles_vector_and_rpc(monkeypatch) -> None:
    from scripts.ingest_feed import _supersede_search_inputs

    monkeypatch.setenv("EMBEDDING_PROFILE", "ilmu_bge_m3")
    monkeypatch.setenv("EMBEDDING_WRITE_PROFILES", "openai,ilmu_bge_m3")
    assert _supersede_search_inputs({"embedding": _OPENAI, "embedding_v2": _BGE}) == ("hybrid_search_v2", _BGE)

    monkeypatch.setenv("EMBEDDING_PROFILE", "openai")
    assert _supersede_search_inputs({"embedding": _OPENAI, "embedding_v2": _BGE}) == ("hybrid_search", _OPENAI)


def test_supersede_search_falls_back_to_a_stored_profile(monkeypatch) -> None:
    from scripts.ingest_feed import _supersede_search_inputs

    monkeypatch.setenv("EMBEDDING_PROFILE", "openai")
    monkeypatch.setenv("EMBEDDING_WRITE_PROFILES", "ilmu_bge_m3")
    assert _supersede_search_inputs({"embedding_v2": _BGE}) == ("hybrid_search_v2", _BGE)


@pytest.mark.asyncio
async def test_grant_rag_does_not_search_the_openai_column_with_another_profiles_vector(monkeypatch) -> None:
    from app.agents.eligibility_agent import grant_rag_node as mod

    monkeypatch.setenv("EMBEDDING_PROFILE", "ilmu_bge_m3")
    supabase = MagicMock()
    table = MagicMock()
    table.select.return_value.eq.return_value.or_.return_value.lte.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )
    supabase.table.return_value = table
    supabase.rpc.return_value.execute = AsyncMock(return_value=MagicMock(data=[{"id": "x"}]))
    embed = AsyncMock(return_value=_BGE)
    with patch.object(mod, "get_cached_result", AsyncMock(return_value=None)), \
            patch.object(mod, "set_cached_result", AsyncMock()), \
            patch.object(mod, "_embed_query", embed):
        result = await mod.grant_rag_node(
            {"business_profile": {"sector": "retail", "business_type": "sdn bhd", "registered_months": 12}},
            supabase,
        )
    assert result["retrieved_grant_chunks"] == []
    supabase.rpc.assert_not_called()
    embed.assert_not_awaited()
