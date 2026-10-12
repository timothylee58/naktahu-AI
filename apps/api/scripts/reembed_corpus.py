#!/usr/bin/env python3
"""Re-embed the corpus with ILMU-hosted bge-m3 into the side-by-side
``embedding_v2`` column (migration 056), and compare retrieval before cutover.

Never touches the live ``embedding`` column. Safe to stop and re-run: only rows
whose ``embedding_v2`` is still NULL are processed.

Usage (from apps/api, normally via .github/workflows/reembed-corpus.yml):

    python -m scripts.reembed_corpus --mode probe
    python -m scripts.reembed_corpus --mode backfill --table all [--limit N] [--dry-run]
    python -m scripts.reembed_corpus --mode compare

Modes:
  probe     Embed a few sentences with the new model and check the dimension
            and basic semantics. Writes nothing. Run this FIRST — it is the
            only thing that proves the model id / key / dimension are right.
  backfill  Embed rows missing embedding_v2 and write them.
  compare   Run the same queries through the current profile (hybrid_search)
            and the new one (hybrid_search_v2) and report top-5 overlap plus
            the Belanjawan 2027 results, so a human can judge quality.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY),
ILMU_API_KEY, ILMU_BASE_URL; compare also needs OPENAI_API_KEY.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from supabase import create_client  # noqa: E402

from app.agents.rag_node import embed_with_profile  # noqa: E402
from app.services.embedding_profiles import PROFILES, EmbeddingProfile  # noqa: E402
from app.services.llm_client import ilmu_client  # noqa: E402
from app.services.madani_scheme_ingest import build_scheme_embedding_text  # noqa: E402
from core.config import settings  # noqa: E402

TARGET = PROFILES["ilmu_bge_m3"]
SOURCE = PROFILES["openai"]
TABLES = ("document_chunks", "madani_scheme")
# bge-m3 accepts ~8k tokens; chunks are far smaller, this only guards outliers.
MAX_CHARS = 24_000
WRITE_CONCURRENCY = 8
EVAL_FILES = ("keyword_recall.jsonl", "answer_quality.jsonl", "tax_accuracy.jsonl")
# What Budget questions look like; printed (not scored) so a human can check
# that the new model retrieves the 2027 documents.
BUDGET_QUERIES = (
    "Belanjawan 2027 apa perubahan cukai pendapatan?",
    "What are the main measures in Budget 2027?",
    "Fiscal outlook 2027 revenue and expenditure",
    "Tinjauan fiskal 2027 defisit fiskal",
)


class ReembedError(RuntimeError):
    pass


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _clip(text: str) -> str:
    return text[:MAX_CHARS]


async def embed_batch(texts: list[str], profile: EmbeddingProfile = TARGET) -> list[list[float]]:
    """One ILMU request for the whole batch; validates count and dimension.

    Returns vectors in input order (OpenAI-compatible responses carry an index).
    """
    resp = await ilmu_client.embeddings.create(model=profile.ilmu_model, input=[_clip(t) for t in texts])
    data = sorted(resp.data, key=lambda d: d.index)
    if len(data) != len(texts):
        raise ReembedError(f"asked for {len(texts)} embeddings, got {len(data)}")
    vectors = [list(d.embedding) for d in data]
    for vec in vectors:
        if len(vec) != profile.dims:
            raise ReembedError(
                f"{profile.ilmu_model} returned {len(vec)} dims, expected {profile.dims} "
                f"(column {profile.column} is vector({profile.dims}))"
            )
    return vectors


async def probe() -> int:
    """Prove the model id, key and dimension work, and that it is semantic."""
    samples = [
        "Bagaimana hendak memohon bantuan kewangan kerajaan?",
        "How do I apply for government financial assistance?",
        "Resepi nasi lemak yang sedap dan mudah",
    ]
    try:
        vecs = await embed_batch(samples)
    except Exception as exc:
        print(f"PROBE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    same = _cosine(vecs[0], vecs[1])
    different = _cosine(vecs[0], vecs[2])
    print(f"model={TARGET.ilmu_model} dims={len(vecs[0])} (expected {TARGET.dims})")
    print(f"cosine(BM, EN same meaning) = {same:.3f}   cosine(BM, unrelated) = {different:.3f}")
    if not same > different:
        print("PROBE FAILED: translated pair is not closer than an unrelated sentence", file=sys.stderr)
        return 1
    print("PROBE OK")
    return 0


def _row_text(table: str, row: dict[str, Any]) -> str:
    if table == "document_chunks":
        return row.get("content") or ""
    return build_scheme_embedding_text(row)


def _count_missing(supabase, table: str) -> int:
    res = supabase.table(table).select("id", count="exact").is_("embedding_v2", "null").limit(1).execute()
    return int(res.count or 0)


async def _write(supabase, table: str, updates: list[tuple[str, list[float]]]) -> int:
    sem = asyncio.Semaphore(WRITE_CONCURRENCY)
    written = 0

    async def one(row_id: str, vec: list[float]) -> None:
        nonlocal written
        async with sem:
            await asyncio.to_thread(
                lambda: supabase.table(table).update({TARGET.column: vec}).eq("id", row_id).execute()
            )
            written += 1

    await asyncio.gather(*(one(i, v) for i, v in updates))
    return written


async def backfill_table(
    supabase, table: str, *, batch_size: int, limit: Optional[int], dry_run: bool
) -> dict[str, int]:
    """Embed rows with a NULL embedding_v2, keyset-paginated so a row that
    cannot be embedded is counted once and skipped rather than retried forever."""
    missing = _count_missing(supabase, table)
    print(f"[{table}] {missing} row(s) without {TARGET.column}")
    stats = {"missing": missing, "embedded": 0, "failed": 0, "skipped_empty": 0}
    if dry_run or missing == 0:
        return stats

    last_id = "00000000-0000-0000-0000-000000000000"
    processed = 0
    while True:
        take = batch_size if limit is None else min(batch_size, limit - processed)
        if take <= 0:
            break
        res = (
            supabase.table(table).select("*").is_("embedding_v2", "null")
            .gt("id", last_id).order("id").limit(take).execute()
        )
        rows = res.data or []
        if not rows:
            break
        last_id = rows[-1]["id"]
        processed += len(rows)

        todo = []
        for row in rows:
            text = _row_text(table, row).strip()
            if text:
                todo.append((row["id"], text))
            else:
                stats["skipped_empty"] += 1
        if not todo:
            continue

        updates: list[tuple[str, list[float]]] = []
        try:
            vectors = await embed_batch([t for _, t in todo])
            updates = [(rid, vec) for (rid, _), vec in zip(todo, vectors)]
        except Exception as exc:
            # One bad row must not sink the batch: retry singly to isolate it.
            print(f"  batch of {len(todo)} failed ({type(exc).__name__}: {str(exc)[:160]}); retrying singly")
            for rid, text in todo:
                try:
                    updates.append((rid, (await embed_batch([text]))[0]))
                except Exception as single_exc:
                    stats["failed"] += 1
                    print(f"  FAILED id={rid}: {type(single_exc).__name__}: {str(single_exc)[:160]}")
        stats["embedded"] += await _write(supabase, table, updates)
        print(f"  [{table}] embedded {stats['embedded']} / {missing}")

    stats["remaining"] = _count_missing(supabase, table)
    print(f"[{table}] done: {stats}")
    return stats


def _load_queries() -> list[str]:
    queries: list[str] = []
    eval_dir = _API_ROOT / "evals"
    for name in EVAL_FILES:
        path = eval_dir / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            q = json.loads(line).get("query")
            if isinstance(q, str) and q.strip():
                queries.append(q.strip())
    return list(dict.fromkeys(queries))


def _search(supabase, profile: EmbeddingProfile, query: str, embedding: list[float]) -> list[dict[str, Any]]:
    res = supabase.rpc(profile.chunks_rpc, {
        "query_text": query, "query_embedding": embedding, "match_count": 5,
    }).execute()
    return res.data or []


async def compare(supabase, queries: Iterable[str]) -> int:
    queries = list(queries)
    overlaps: list[float] = []
    top1_same = 0
    scored = 0
    print(f"Comparing {SOURCE.name} vs {TARGET.name} on {len(queries)} eval queries (top-5 by id)\n")
    for q in queries:
        try:
            old = _search(supabase, SOURCE, q, await embed_with_profile(q, SOURCE))
            new = _search(supabase, TARGET, q, await embed_with_profile(q, TARGET))
        except Exception as exc:
            print(f"  SKIP {q[:60]!r}: {type(exc).__name__}: {str(exc)[:120]}")
            continue
        old_ids, new_ids = [r["id"] for r in old], [r["id"] for r in new]
        if not old_ids and not new_ids:
            continue
        scored += 1
        overlaps.append(len(set(old_ids) & set(new_ids)) / max(len(old_ids), len(new_ids)))
        if old_ids and new_ids and old_ids[0] == new_ids[0]:
            top1_same += 1
    if scored:
        print(f"queries scored: {scored}   mean top-5 overlap: {sum(overlaps) / scored:.2f}   "
              f"same top-1: {top1_same}/{scored}")
    else:
        print("No query returned results under either profile.")

    print("\nBudget 2027 spot-check (new model):")
    ok = True
    for q in BUDGET_QUERIES:
        try:
            rows = _search(supabase, TARGET, q, await embed_with_profile(q, TARGET))
        except Exception as exc:
            print(f"  {q!r}: ERROR {type(exc).__name__}: {str(exc)[:120]}")
            ok = False
            continue
        print(f"  {q!r}")
        for r in rows[:3]:
            print(f"    - {r['source_title'][:70]}  [{r['source_url'][:70]}]")
        if not rows:
            ok = False
    return 0 if (scored and ok) else 1


async def run(args: argparse.Namespace) -> int:
    if args.mode == "probe":
        return await probe()
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    if args.mode == "compare":
        return await compare(supabase, _load_queries())

    rc = await probe()
    if rc:
        print("Refusing to backfill: probe failed.", file=sys.stderr)
        return rc
    tables = TABLES if args.table == "all" else (args.table,)
    failed = 0
    for table in tables:
        stats = await backfill_table(
            supabase, table, batch_size=args.batch_size, limit=args.limit, dry_run=args.dry_run
        )
        failed += stats["failed"]
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["probe", "backfill", "compare"], required=True)
    parser.add_argument("--table", choices=[*TABLES, "all"], default="all")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=None, help="max rows per table (backfill)")
    parser.add_argument("--dry-run", action="store_true", help="backfill: only count rows missing embedding_v2")
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 128:
        parser.error("--batch-size must be between 1 and 128")
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
