"""Upload embedded chunks to Supabase document_chunks table.

Reads  : scripts/ingest/data/processed/chunks.jsonl
Upserts: Supabase document_chunks on content_hash (idempotent reruns)

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

# Columns accepted by the document_chunks table
_ALLOWED_COLS = {
    "id", "content", "content_hash", "language", "domain",
    "source_title", "source_url", "ministry", "embedding",
    "expiry_aware", "source_date",
}


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


def _prepare_row(chunk: dict) -> dict:
    row = {k: v for k, v in chunk.items() if k in _ALLOWED_COLS}
    if isinstance(row.get("embedding"), list):
        row["embedding"] = "[" + ",".join(str(v) for v in row["embedding"]) + "]"
    # Ensure booleans are correct type
    row["expiry_aware"] = bool(row.get("expiry_aware", False))
    # source_date: keep as ISO string or None — Supabase accepts both
    if not row.get("source_date"):
        row["source_date"] = None
    return row


def upload(client: Client, chunks: list[dict]) -> tuple[int, int]:
    inserted = 0
    errors = 0

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = [_prepare_row(c) for c in chunks[i : i + BATCH_SIZE]]
        try:
            result = (
                client.table(TABLE)
                .upsert(batch, on_conflict="content_hash")
                .execute()
            )
            count = len(result.data) if result.data else len(batch)
            inserted += count
            log.info(
                "batch_upserted",
                batch_num=i // BATCH_SIZE + 1,
                count=count,
                total_so_far=inserted,
            )
        except Exception as exc:
            errors += len(batch)
            log.error(
                "batch_upsert_failed",
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

    # Summary before upload
    from collections import Counter
    domain_counts = Counter(c.get("domain", "unknown") for c in chunks)
    expiry_count = sum(1 for c in chunks if c.get("expiry_aware"))
    log.info("chunk_summary", by_domain=dict(domain_counts), expiry_aware=expiry_count)

    inserted, errors = upload(client, chunks)
    log.info("upload_complete", inserted=inserted, errors=errors, total=len(chunks))

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
