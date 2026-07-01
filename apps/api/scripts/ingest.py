"""
Ingest DOSM CSV files into Supabase dosm_documents with OpenAI embeddings.

Usage:
    python -m scripts.ingest --dir data/dosm/
    python -m scripts.ingest --dir data/dosm/ --batch-size 50 --dry-run

Expected CSV columns (all optional except 'content'):
    content      Text to embed and retrieve
    dataset      Dataset name, e.g. "Population by State 2020"
    year         Publication year
    ministry     Producing ministry (default: DOSM)
    url          Source URL
    source_title Human-readable title (falls back to dataset)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from dotenv import load_dotenv
from supabase import create_client

from app.middleware.sanitise import INJECTION_PATTERNS

load_dotenv()

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
TABLE = "dosm_documents"
DEFAULT_BATCH = 100
RATE_LIMIT_PAUSE = 0.5  # seconds between embedding batches


# ---------------------------------------------------------------------------
# Injection scan — reuses the exact pattern list applied to user queries in
# app/middleware/sanitise.py (INJECTION_PATTERNS), so poisoned rows in an
# ingested CSV cannot smuggle an indirect prompt injection into
# document_chunks/dosm_documents and later into synthesiser_node's context,
# bypassing the user-facing input sanitiser entirely.
# ---------------------------------------------------------------------------

def _scan_for_injection(content: str) -> str | None:
    """Return the matched pattern string if content looks like a prompt
    injection attempt, else None. Scans an NFKC-normalised copy so full-width
    / compatibility-character evasion can't dodge the same regexes used on
    the query side."""
    text = unicodedata.normalize("NFKC", content)
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def _require_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"ERROR: environment variable {name} is not set.", file=sys.stderr)
        sys.exit(1)
    return val


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    if "content" not in df.columns:
        raise ValueError(f"{path.name}: missing required column 'content'")
    return df


def row_to_record(row: pd.Series, source_file: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source_file": source_file,
        "dataset": row.get("dataset", ""),
        "year": row.get("year", ""),
        "ministry": row.get("ministry", "DOSM") or "DOSM",
        "url": row.get("url", ""),
        "source_title": row.get("source_title", "") or row.get("dataset", ""),
    }
    return {"content": row["content"], "metadata": metadata}


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str], api_key: str) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def upsert_batch(
    supabase_client: Any,
    records: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> int:
    rows = [
        {
            "content": rec["content"],
            "metadata": rec["metadata"],
            "embedding": emb,
        }
        for rec, emb in zip(records, embeddings)
    ]
    result = supabase_client.table(TABLE).insert(rows).execute()
    return len(result.data) if result.data else 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest DOSM CSVs into Supabase pgvector")
    parser.add_argument("--dir", default="data/dosm", help="Directory containing CSVs")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH, dest="batch_size")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and embed but do not write to Supabase",
    )
    parser.add_argument(
        "--file",
        help="Ingest a single CSV file instead of the whole directory",
    )
    args = parser.parse_args()

    openai_key = _require_env("OPENAI_API_KEY")
    supabase_url = _require_env("SUPABASE_URL")
    supabase_key = _require_env("SUPABASE_SERVICE_KEY")

    supabase = None if args.dry_run else create_client(supabase_url, supabase_key)

    # Collect CSV paths
    if args.file:
        csv_paths = [Path(args.file)]
    else:
        csv_paths = sorted(Path(args.dir).glob("*.csv"))

    if not csv_paths:
        print(f"No CSV files found in {args.dir}. Add DOSM CSVs and retry.")
        sys.exit(0)

    total_inserted = 0
    total_errors = 0
    total_skipped_injection = 0

    for csv_path in csv_paths:
        print(f"\n{'─'*60}")
        print(f"File: {csv_path.name}")
        try:
            df = load_csv(csv_path)
        except (ValueError, Exception) as exc:
            print(f"  SKIP — {exc}")
            total_errors += 1
            continue

        # Drop rows with empty content
        df = df[df["content"].str.strip() != ""]

        # Scan each row's content for prompt-injection patterns BEFORE it is
        # embedded or written to Supabase. Matching rows are skipped (not the
        # whole batch/file) so one poisoned CSV row can't block ingestion of
        # the rest of the dataset. This runs identically in --dry-run so
        # operators can preview what would be skipped without writing.
        clean_rows = []
        skipped_injection = 0
        for row_num, (_, row) in enumerate(df.iterrows(), start=1):
            matched = _scan_for_injection(str(row["content"]))
            if matched:
                skipped_injection += 1
                log.warning(
                    "ingest_row_skipped_injection_suspected",
                    dataset=csv_path.name,
                    row_number=row_num,
                    matched_pattern=matched,
                    dry_run=args.dry_run,
                )
                continue
            clean_rows.append(row)

        total_skipped_injection += skipped_injection
        print(f"  Rows to ingest: {len(clean_rows)}"
              + (f" ({skipped_injection} skipped — injection suspected, see logs)" if skipped_injection else ""))

        records = [row_to_record(row, csv_path.name) for row in clean_rows]
        texts = [r["content"] for r in records]

        # Process in batches
        for i in range(0, len(records), args.batch_size):
            batch_records = records[i : i + args.batch_size]
            batch_texts = texts[i : i + args.batch_size]
            batch_num = i // args.batch_size + 1
            total_batches = (len(records) + args.batch_size - 1) // args.batch_size

            print(f"  Batch {batch_num}/{total_batches} — embedding {len(batch_texts)} rows …", end=" ", flush=True)
            try:
                vecs = embed_texts(batch_texts, openai_key)
            except Exception as exc:
                print(f"FAILED (embedding): {exc}")
                total_errors += 1
                continue

            if args.dry_run:
                print(f"OK (dry-run, {len(vecs)} vectors generated)")
            else:
                try:
                    n = upsert_batch(supabase, batch_records, vecs)
                    print(f"OK ({n} rows inserted)")
                    total_inserted += n
                except Exception as exc:
                    print(f"FAILED (upsert): {exc}")
                    total_errors += 1

            if i + args.batch_size < len(records):
                time.sleep(RATE_LIMIT_PAUSE)

    print(f"\n{'='*60}")
    if total_skipped_injection:
        print(f"Skipped {total_skipped_injection} row(s) — prompt-injection pattern suspected (see warnings above).")
    if args.dry_run:
        print("Dry-run complete — no data written to Supabase.")
    else:
        print(f"Ingestion complete: {total_inserted} rows inserted, {total_errors} errors.")


if __name__ == "__main__":
    main()
