"""
Backfill document_chunks.embedding_ilmu for rows that don't have one yet.

Run after applying migration 051 (and again whenever rows were ingested
while ILMU was unavailable — ingest_feed.py leaves embedding_ilmu NULL rather
than failing, and upload_parliament.py only writes the OpenAI column).

Until a row is backfilled it is invisible to hybrid_search_ilmu, and
rag_node falls back to the OpenAI column for queries — so running this is
what actually switches retrieval over to ILMU-first.

Only ever writes ILMU vectors into embedding_ilmu (see llm_client.py's
dual-embedding invariant); never touches the OpenAI `embedding` column.

Usage:
    python -m scripts.backfill_ilmu_embeddings --dry-run
    python -m scripts.backfill_ilmu_embeddings
    python -m scripts.backfill_ilmu_embeddings --limit 100
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.agents.rag_node import _embed_ilmu  # noqa: E402
from core.config import settings  # noqa: E402

load_dotenv()

_PAGE_SIZE = 50


def _fetch_missing(supabase, limit: int | None) -> list[dict]:
    """All rows with embedding_ilmu IS NULL (paged), up to `limit` if given."""
    rows: list[dict] = []
    offset = 0
    while True:
        page_size = _PAGE_SIZE if limit is None else min(_PAGE_SIZE, limit - len(rows))
        if page_size <= 0:
            break
        resp = (
            supabase.table("document_chunks")
            .select("id,content")
            .is_("embedding_ilmu", "null")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = resp.data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


async def run(args: argparse.Namespace) -> int:
    if not settings.supabase_url or not settings.supabase_service_key:
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — nothing to do.")
        return 1
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    try:
        rows = _fetch_missing(supabase, args.limit)
    except Exception as exc:
        # The usual cause: migration 051 not applied, so the column is missing.
        print(f"Could not read embedding_ilmu — is migration 051 applied? ({exc})")
        return 1

    print(f"{len(rows)} row(s) missing an ILMU embedding{' (dry-run)' if args.dry_run else ''}")
    done = failed = 0
    for row in rows:
        try:
            vector = await _embed_ilmu(row["content"])
        except Exception as exc:
            failed += 1
            print(f"  FAILED (ILMU embed) {row['id']}: {exc}")
            # A wrong ILMU_EMBEDDING_MODEL or dimension fails identically for
            # every row — stop after the first rather than burning N calls.
            if failed == 1 and done == 0:
                print("  First row failed — aborting. Check ILMU_EMBEDDING_MODEL / ILMU_API_KEY.")
                break
            continue
        if args.dry_run:
            done += 1
            continue
        try:
            supabase.table("document_chunks").update({"embedding_ilmu": vector}).eq("id", row["id"]).execute()
            done += 1
        except Exception as exc:
            failed += 1
            print(f"  FAILED (update) {row['id']}: {exc}")

    verb = "would be backfilled" if args.dry_run else "backfilled"
    print(f"{done} {verb}, {failed} failed.")
    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill document_chunks.embedding_ilmu")
    parser.add_argument("--dry-run", action="store_true", help="Embed with ILMU but write nothing")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to process")
    sys.exit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
