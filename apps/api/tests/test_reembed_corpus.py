"""scripts/reembed_corpus.py — embed_batch validation, probe, resumable backfill,
and migration 056's agreement with the profile table."""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding_profiles import PROFILES
from scripts import reembed_corpus as rc

_VEC = [0.1] * 1024


def _resp(vectors: list[list[float]], *, shuffled: bool = False) -> MagicMock:
    items = []
    for i, vec in enumerate(vectors):
        item = MagicMock()
        item.embedding = vec
        item.index = i
        items.append(item)
    resp = MagicMock()
    resp.data = list(reversed(items)) if shuffled else items
    return resp


class FakeTable:
    """Just enough of the supabase query builder for backfill_table."""

    def __init__(self, store: "FakeSupabase", name: str) -> None:
        self.store, self.name = store, name
        self._count = False
        self._null = False
        self._gt: str | None = None
        self._limit: int | None = None
        self._update: dict | None = None
        self._eq: str | None = None

    def select(self, *_cols, count=None):
        self._count = bool(count)
        return self

    def is_(self, _col, _val):
        self._null = True
        return self

    def gt(self, _col, value):
        self._gt = value
        return self

    def order(self, _col):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def update(self, values):
        self._update = values
        return self

    def eq(self, _col, value):
        self._eq = value
        return self

    def execute(self):
        rows = self.store.rows[self.name]
        if self._update is not None:
            for row in rows:
                if row["id"] == self._eq:
                    row.update(self._update)
            return MagicMock(data=[])
        matching = [r for r in rows if (not self._null or r.get("embedding_v2") is None)]
        if self._count:
            return MagicMock(count=len(matching), data=matching[:1])
        matching = [r for r in sorted(matching, key=lambda r: r["id"]) if not self._gt or r["id"] > self._gt]
        return MagicMock(data=matching[: self._limit])


class FakeSupabase:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self.rows = rows

    def table(self, name: str) -> FakeTable:
        return FakeTable(self, name)


def _chunks(n: int, **extra) -> list[dict]:
    return [{"id": f"00000000-0000-0000-0000-{i:012d}", "content": f"teks {i}", "embedding_v2": None, **extra}
            for i in range(1, n + 1)]


# ── embed_batch ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_embed_batch_returns_vectors_in_input_order() -> None:
    a, b = [0.1] * 1024, [0.2] * 1024
    ilmu = MagicMock()
    ilmu.embeddings.create = AsyncMock(return_value=_resp([a, b], shuffled=True))
    with patch.object(rc, "ilmu_client", ilmu):
        assert await rc.embed_batch(["a", "b"]) == [a, b]
    assert ilmu.embeddings.create.await_args.kwargs["model"] == "bge-m3"


@pytest.mark.asyncio
async def test_embed_batch_rejects_wrong_dimension_and_count() -> None:
    ilmu = MagicMock()
    ilmu.embeddings.create = AsyncMock(return_value=_resp([[0.1] * 4096]))
    with patch.object(rc, "ilmu_client", ilmu), pytest.raises(rc.ReembedError, match="4096 dims, expected 1024"):
        await rc.embed_batch(["a"])
    ilmu.embeddings.create = AsyncMock(return_value=_resp([_VEC]))
    with patch.object(rc, "ilmu_client", ilmu), pytest.raises(rc.ReembedError, match="asked for 2"):
        await rc.embed_batch(["a", "b"])


# ── probe ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_probe_passes_when_translation_is_closer_than_unrelated(capsys) -> None:
    near, far = [1.0] + [0.0] * 1023, [0.0, 1.0] + [0.0] * 1022
    with patch.object(rc, "embed_batch", AsyncMock(return_value=[near, near, far])):
        assert await rc.probe() == 0
    assert "PROBE OK" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_probe_fails_on_api_error_or_non_semantic_vectors(capsys) -> None:
    with patch.object(rc, "embed_batch", AsyncMock(side_effect=RuntimeError("model_not_found"))):
        assert await rc.probe() == 1
    assert "PROBE FAILED" in capsys.readouterr().err
    same = [1.0] + [0.0] * 1023
    with patch.object(rc, "embed_batch", AsyncMock(return_value=[same, [0.0, 1.0] + [0.0] * 1022, same])):
        assert await rc.probe() == 1


# ── backfill ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_fills_only_embedding_v2_and_is_resumable() -> None:
    rows = _chunks(5)
    rows[0]["embedding_v2"] = _VEC  # already done: must be left alone
    rows[0]["embedding"] = "live-vector"
    sb = FakeSupabase({"document_chunks": rows})
    embed = AsyncMock(side_effect=lambda texts, *a, **k: [_VEC for _ in texts])
    with patch.object(rc, "embed_batch", embed):
        stats = await rc.backfill_table(sb, "document_chunks", batch_size=2, limit=None, dry_run=False)
    assert stats["embedded"] == 4 and stats["failed"] == 0 and stats["remaining"] == 0
    assert all(r["embedding_v2"] == _VEC for r in rows)
    assert rows[0]["embedding"] == "live-vector"  # the live column is never written
    assert all("embedding" not in r for r in rows[1:])
    # Already-done row was not re-embedded: 4 texts over 2 batches.
    assert sum(len(c.args[0]) for c in embed.await_args_list) == 4


@pytest.mark.asyncio
async def test_backfill_isolates_a_bad_row_instead_of_failing_the_batch() -> None:
    rows = _chunks(3)
    rows[1]["content"] = "poison"
    sb = FakeSupabase({"document_chunks": rows})

    async def fake_embed(texts, *a, **k):
        if "poison" in texts:
            raise rc.ReembedError("cannot embed")
        return [_VEC for _ in texts]

    with patch.object(rc, "embed_batch", AsyncMock(side_effect=fake_embed)):
        stats = await rc.backfill_table(sb, "document_chunks", batch_size=3, limit=None, dry_run=False)
    assert stats["embedded"] == 2 and stats["failed"] == 1 and stats["remaining"] == 1
    assert rows[1]["embedding_v2"] is None


@pytest.mark.asyncio
async def test_backfill_does_not_loop_forever_on_a_row_that_never_embeds() -> None:
    rows = _chunks(2)
    sb = FakeSupabase({"document_chunks": rows})
    with patch.object(rc, "embed_batch", AsyncMock(side_effect=rc.ReembedError("nope"))):
        stats = await rc.backfill_table(sb, "document_chunks", batch_size=1, limit=None, dry_run=False)
    assert stats["failed"] == 2 and stats["embedded"] == 0


@pytest.mark.asyncio
async def test_backfill_dry_run_writes_nothing_and_calls_no_api() -> None:
    sb = FakeSupabase({"document_chunks": _chunks(3)})
    embed = AsyncMock()
    with patch.object(rc, "embed_batch", embed):
        stats = await rc.backfill_table(sb, "document_chunks", batch_size=2, limit=None, dry_run=True)
    assert stats["missing"] == 3 and stats["embedded"] == 0
    embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_respects_limit_and_skips_empty_content() -> None:
    rows = _chunks(5)
    rows[0]["content"] = "   "
    sb = FakeSupabase({"document_chunks": rows})
    with patch.object(rc, "embed_batch", AsyncMock(side_effect=lambda texts, *a, **k: [_VEC for _ in texts])):
        stats = await rc.backfill_table(sb, "document_chunks", batch_size=10, limit=3, dry_run=False)
    assert stats["skipped_empty"] == 1 and stats["embedded"] == 2
    assert rows[0]["embedding_v2"] is None and rows[3]["embedding_v2"] is None


@pytest.mark.asyncio
async def test_backfill_madani_embeds_the_same_text_ingest_uses() -> None:
    row = {"id": "00000000-0000-0000-0000-000000000001", "scheme_name": "Bantuan X", "description": "Huraian",
           "category": "bantuan", "scope": "national", "embedding_v2": None}
    sb = FakeSupabase({"madani_scheme": [row]})
    embed = AsyncMock(side_effect=lambda texts, *a, **k: [_VEC for _ in texts])
    with patch.object(rc, "embed_batch", embed):
        await rc.backfill_table(sb, "madani_scheme", batch_size=4, limit=None, dry_run=False)
    from app.services.madani_scheme_ingest import build_scheme_embedding_text

    assert embed.await_args.args[0] == [build_scheme_embedding_text(row)]
    assert row["embedding_v2"] == _VEC


@pytest.mark.asyncio
async def test_run_backfill_refuses_when_probe_fails() -> None:
    args = MagicMock(mode="backfill", table="all", batch_size=8, limit=None, dry_run=False)
    with patch.object(rc, "create_client", MagicMock()), patch.object(rc, "probe", AsyncMock(return_value=1)), \
            patch.object(rc, "backfill_table", AsyncMock()) as backfill:
        assert await rc.run(args) == 1
    backfill.assert_not_awaited()


# ── migration 056 ↔ profile table ─────────────────────────────────────────

_MIGRATION = Path(__file__).resolve().parents[3] / "infra" / "supabase" / "migrations" / "056_embedding_v2_bge_m3.sql"


def test_migration_056_matches_the_bge_profile() -> None:
    sql = _MIGRATION.read_text(encoding="utf-8")
    profile = PROFILES["ilmu_bge_m3"]
    assert f"embedding_v2 vector({profile.dims})" in sql
    assert f"FUNCTION {profile.chunks_rpc}(" in sql
    assert f"FUNCTION {profile.madani_rpc}(" in sql
    assert profile.column == "embedding_v2"


def test_migration_056_is_additive_and_leaves_the_live_column_alone() -> None:
    sql = _MIGRATION.read_text(encoding="utf-8")
    code = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    assert not re.search(r"\bDROP\b|\bTRUNCATE\b|\bDELETE\b", code, re.IGNORECASE)
    assert not re.search(r"ALTER\s+COLUMN\s+embedding\b", code, re.IGNORECASE)
    assert "CREATE OR REPLACE FUNCTION hybrid_search(" not in code  # original RPC untouched
    assert code.count("ADD COLUMN IF NOT EXISTS embedding_v2") == 2


# ── compare ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compare_reports_overlap_and_budget_results(capsys) -> None:
    def fake_search(_sb, profile, _q, _emb):
        ids = ["a", "b", "c"] if profile.name == "openai" else ["a", "b", "z"]
        return [{"id": i, "source_title": f"Title {i}", "source_url": f"https://www.mof.gov.my/{i}"} for i in ids]

    with patch.object(rc, "_search", side_effect=fake_search), \
            patch.object(rc, "embed_with_profile", AsyncMock(return_value=[0.0])):
        rc_code = await rc.compare(MagicMock(), ["q1", "q2"])
    out = capsys.readouterr().out
    assert rc_code == 0
    assert "mean top-5 overlap: 0.67" in out and "same top-1: 2/2" in out
    assert "Budget 2027 spot-check" in out and "mof.gov.my" in out


@pytest.mark.asyncio
async def test_compare_fails_when_the_new_profile_returns_nothing() -> None:
    def fake_search(_sb, profile, _q, _emb):
        return [{"id": "a", "source_title": "t", "source_url": "u"}] if profile.name == "openai" else []

    with patch.object(rc, "_search", side_effect=fake_search), \
            patch.object(rc, "embed_with_profile", AsyncMock(return_value=[0.0])):
        assert await rc.compare(MagicMock(), ["q1"]) == 1
