"""Upload embedded chunks to Supabase document_chunks table.

Reads  : scripts/ingest/data/processed/chunks.jsonl
Inserts: Supabase document_chunks (upserts on id to be idempotent)

Run:
    python scripts/ingest/upload_to_supabase.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import structlog
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent.parent / "apps" / "api" / ".env")

CHUNKS_FILE = Path(__file__).parent / "data" / "processed" / "chunks.jsonl"
BATCH_SIZE = 100
TABLE = "document_chunks"

log = structlog.get_logger(__name__)


def load_chunks() -> list[dict]:
    if not CHUNKS_FILE.exists():
        log.error("chunks_file_not_found", path=str(CHUNKS_FILE))
        sys.exit(1)

    chunks = []
    with CHUNKS_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def upload(client: Client, chunks: list[dict]) -> tuple[int, int]:
    inserted = 0
    errors = 0

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        # Convert embedding list to pgvector-compatible string representation
        for chunk in batch:
            if isinstance(chunk.get("embedding"), list):
                chunk["embedding"] = "[" + ",".join(str(v) for v in chunk["embedding"]) + "]"

        try:
            result = (
                client.table(TABLE)
                .upsert(batch, on_conflict="id")
                .execute()
            )
            count = len(result.data) if result.data else len(batch)
            inserted += count
            log.info(
                "batch_inserted",
                batch_num=i // BATCH_SIZE + 1,
                count=count,
                total_so_far=inserted,
            )
        except Exception as exc:
            errors += len(batch)
            log.error(
                "batch_insert_failed",
                batch_num=i // BATCH_SIZE + 1,
                error=str(exc),
            )

    return inserted, errors


def main() -> None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.error("missing_env_vars", vars=["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"])
        sys.exit(1)

    client = create_client(url, key)
    chunks = load_chunks()
    log.info("loaded_chunks", count=len(chunks))

    inserted, errors = upload(client, chunks)

    log.info(
        "upload_complete",
        inserted=inserted,
        errors=errors,
        total=len(chunks),
    )

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
