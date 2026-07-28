"""
scripts/ingest_parliament/upload_parliament.py

Step 4 (final) of the Hansard ingestion pipeline.
Reads processed JSONL files and uploads to Supabase.

What it does:
  1. Inserts mp_statements rows (links mp_id via name lookup, carries
     match_confidence/match_strategy from link_mp_profiles.py).
  2. Inserts mp_votes rows (source_verified is ALWAYS false — this pipeline
     ingests unverified scraped data; verification is a human step).
  3. Chunks mp_statements into document_chunks for RAG (domain='hansard'),
     after an injection scan and content_hash dedup identical in mechanism
     to scripts/ingest_feed.py's.
  4. Generates embeddings via the shared app.agents.rag_node._embed
     (ILMU -> OpenAI fallback) — no hand-rolled embedding client.
  5. Marks hansard_sittings.ingested=true on completion.
  6. Updates mp_profiles computed scores (questions_count, motions_count).

Fixes made relative to the originally pasted script (see PR body / commit
message for the full list): injection scan before embed/insert (hard rule,
CLAUDE.md — no ingestion path is exempt), content_hash dedup via the same
UNIQUE-index contract as ingest_feed.py (replacing a bespoke _chunk_id()
hash-as-PK scheme, which duplicated content on file_content_hash so
re-running an already-ingested sitting was NOT a cheap no-op), reuse of
app.agents.rag_node._embed instead of a raw AsyncOpenAI client, dropping the
nonexistent document_chunks.bill_number field (mp_statements.bill_number
already carries it — chunks aren't a queryable-by-bill surface), and
match_confidence/match_strategy threading so fuzzy-matched (lowest-trust)
attributions are visible in the pipeline summary rather than silent.

Run: python -m scripts.ingest_parliament.upload_parliament
     python -m scripts.ingest_parliament.upload_parliament --sitting-date 2025-07-07
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.agents.rag_node import _embed  # noqa: E402 — reuse the live ILMU->OpenAI embedding fallback
from app.middleware.sanitise import INJECTION_PATTERNS, _fold_confusables  # noqa: E402
from core.config import settings  # noqa: E402

log = structlog.get_logger(__name__)

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
STATEMENTS_FILE = PROCESSED_DIR / "hansard_statements.jsonl"
VOTES_FILE = PROCESSED_DIR / "hansard_votes.jsonl"
LOOKUP_FILE = PROCESSED_DIR / "mp_name_lookup.json"

CHUNK_SIZE = 512     # words (approximate token proxy — matches the pasted script's intent)
CHUNK_OVERLAP = 64
BATCH_SIZE = 50       # Supabase insert batch size
EMBED_CONCURRENCY = 8  # concurrent _embed() calls (it takes one string at a time)


def _chunk_text(text: str, max_words: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += max_words - overlap
    return chunks


def _scan_for_injection(content: str) -> Optional[str]:
    """Identical mechanism to scripts/ingest_feed.py::_scan_for_injection.
    Externally-sourced text scraped from a government PDF is exactly the
    threat model INJECTION_PATTERNS exists for — no ingestion path is
    exempt (CLAUDE.md hard rule)."""
    text = _fold_confusables(unicodedata.normalize("NFKC", content))
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


async def _embed_many(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts via the shared _embed(), bounded by a semaphore
    since _embed() takes one string per call (no batch variant in this
    codebase currently)."""
    sem = asyncio.Semaphore(EMBED_CONCURRENCY)

    async def _one(text: str) -> list[float]:
        async with sem:
            return await _embed(text)

    return await asyncio.gather(*(_one(t) for t in texts))


def _existing_hashes(supabase, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    res = supabase.table("document_chunks").select("content_hash").in_("content_hash", hashes).execute()
    return {row["content_hash"] for row in (res.data or [])}


async def upload_statements(
    supabase,
    statements: list[dict],
    name_lookup: dict[str, dict],
    sitting_date_filter: str | None = None,
) -> dict[str, int]:
    """Insert mp_statements and corresponding document_chunks.
    Returns a summary counter dict."""
    if sitting_date_filter:
        statements = [s for s in statements if s["sitting_date"] == sitting_date_filter]

    log.info("uploading_statements", count=len(statements))
    stats = {
        "statements_inserted": 0,
        "statements_fuzzy_low_confidence": 0,
        "statements_unresolved_skipped": 0,
        "chunks_inserted": 0,
        "chunks_skipped_injection": 0,
        "chunks_skipped_duplicate": 0,
    }

    for i in range(0, len(statements), BATCH_SIZE):
        batch = statements[i:i + BATCH_SIZE]

        stmt_rows = []
        # (text, metadata) pairs pending injection-scan + dedup + embed
        chunk_candidates: list[tuple[str, dict]] = []

        for s in batch:
            match = name_lookup.get(s.get("mp_name", ""))
            if not match:
                stats["statements_unresolved_skipped"] += 1
                continue
            mp_id = match["mp_id"]
            strategy = match.get("strategy", "fuzzy")
            confidence = match.get("confidence", 0.0)
            if strategy == "fuzzy":
                stats["statements_fuzzy_low_confidence"] += 1
                log.info(
                    "statement_matched_low_confidence",
                    mp_name=s.get("mp_name", ""),
                    mp_id=mp_id,
                    confidence=confidence,
                    sitting_date=s.get("sitting_date"),
                )

            stmt_rows.append({
                "mp_id": mp_id,
                "sitting_id": s["sitting_id"],
                "sitting_date": s["sitting_date"],
                "parliament_no": s.get("parliament_no", 15),
                "session_no": s.get("session_no", 1),
                "statement_type": s.get("statement_type", "debate"),
                "topic_category": s.get("topic_category", "general"),
                "statement_bm": s.get("statement_bm", ""),
                "word_count": s.get("word_count", 0),
                "bill_number": s.get("bill_number"),
                "source_url": s.get("source_url", ""),
                "match_confidence": confidence,
                "match_strategy": strategy,
            })

            full_text = s.get("statement_bm") or ""
            for chunk_text in _chunk_text(full_text):
                chunk_candidates.append((chunk_text, {
                    "mp_name": s.get("mp_name", ""),
                    "sitting_date": s["sitting_date"],
                    "source_url": s.get("source_url", ""),
                }))

        if stmt_rows:
            supabase.table("mp_statements").upsert(stmt_rows).execute()
            stats["statements_inserted"] += len(stmt_rows)

        # ── Injection scan (hard rule — every chunk, no exceptions) ────────
        scanned: list[tuple[str, dict, str]] = []  # (text, meta, content_hash)
        for text, meta in chunk_candidates:
            matched = _scan_for_injection(text)
            if matched:
                stats["chunks_skipped_injection"] += 1
                log.warning(
                    "hansard_chunk_skipped_injection_suspected",
                    mp_name=meta["mp_name"],
                    sitting_date=meta["sitting_date"],
                    source_url=meta["source_url"],
                    matched_pattern=matched,
                )
                continue
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            scanned.append((text, meta, content_hash))

        if not scanned:
            continue

        # ── content_hash dedup — same UNIQUE-index contract as ingest_feed.py ──
        existing = _existing_hashes(supabase, [h for _, _, h in scanned])
        to_embed = [(t, m, h) for t, m, h in scanned if h not in existing]
        stats["chunks_skipped_duplicate"] += len(scanned) - len(to_embed)

        if not to_embed:
            continue

        embeddings = await _embed_many([t for t, _, _ in to_embed])

        chunk_inserts = []
        for (text, meta, content_hash), embedding in zip(to_embed, embeddings):
            chunk_inserts.append({
                "content": text,
                "content_hash": content_hash,
                "language": "bm",
                "domain": "hansard",
                "source_title": f"Hansard DR {meta['sitting_date']} — {meta['mp_name']}",
                "source_url": meta["source_url"],
                "ministry": "Parlimen Malaysia",
                "embedding": embedding,
                "effective_date": meta["sitting_date"],
                "expiry_aware": False,
            })

        supabase.table("document_chunks").insert(chunk_inserts).execute()
        stats["chunks_inserted"] += len(chunk_inserts)

    log.info("statements_uploaded", **stats)
    return stats


async def upload_votes(
    supabase,
    votes: list[dict],
    name_lookup: dict[str, dict],
    bill_lookup: dict[str, str],  # {bill_number: bill_id}
    sitting_date_filter: str | None = None,
) -> int:
    """Insert mp_votes rows. source_verified is ALWAYS false — this pipeline
    ingests unverified scraped data; never set True here."""
    if sitting_date_filter:
        votes = [v for v in votes if v["sitting_date"] == sitting_date_filter]

    inserted = 0
    vote_rows = []

    for v in votes:
        match = name_lookup.get(v.get("mp_name", ""))
        if not match:
            continue
        mp_id = match["mp_id"]

        bill_number = v.get("bill_number")
        bill_id = bill_lookup.get(bill_number) if bill_number else None

        vote_rows.append({
            "mp_id": mp_id,
            "bill_id": bill_id,
            "bill_number": bill_number,
            "vote": v.get("vote", "absent"),
            "vote_date": v["sitting_date"],
            "sitting_id": f"DR.{v['sitting_date']}",
            "source_url": v.get("source_url", ""),
            "source_verified": False,  # never set True by this pipeline — manual step
        })

    if vote_rows:
        for i in range(0, len(vote_rows), BATCH_SIZE):
            supabase.table("mp_votes").upsert(
                vote_rows[i:i + BATCH_SIZE],
                on_conflict="mp_id,bill_id,reading_stage",
            ).execute()
        inserted = len(vote_rows)

    log.info("votes_uploaded", inserted=inserted)
    return inserted


def _update_mp_scores(supabase, affected_mp_ids: list[str]) -> None:
    """Recompute and update questions_count, motions_count for affected MPs."""
    for mp_id in set(affected_mp_ids):
        q_count = supabase.table("mp_statements")\
            .select("id", count="exact")\
            .eq("mp_id", mp_id)\
            .in_("statement_type", ["oral_question", "written_question"])\
            .execute()

        m_count = supabase.table("mp_statements")\
            .select("id", count="exact")\
            .eq("mp_id", mp_id)\
            .eq("statement_type", "motion")\
            .execute()

        supabase.table("mp_profiles").update({
            "questions_count": q_count.count or 0,
            "motions_count": m_count.count or 0,
            "last_score_updated": datetime.utcnow().isoformat(),
        }).eq("id", mp_id).execute()


def _mark_sitting_ingested(supabase, sitting_dates: list[str]) -> None:
    for sitting_date in sitting_dates:
        sitting_id = f"DR.{sitting_date}"
        supabase.table("hansard_sittings").update({
            "ingested": True,
            "ingested_at": datetime.utcnow().isoformat(),
        }).eq("sitting_id", sitting_id).execute()


async def main(sitting_date_filter: str | None = None) -> None:
    from supabase import create_client

    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    if not STATEMENTS_FILE.exists():
        log.error("statements_file_missing")
        return
    if not LOOKUP_FILE.exists():
        log.error("lookup_file_missing_run_link_mp_profiles_first")
        return

    with open(LOOKUP_FILE) as f:
        name_lookup: dict[str, dict] = json.load(f)

    statements: list[dict] = []
    with open(STATEMENTS_FILE) as f:
        for line in f:
            statements.append(json.loads(line.strip()))

    votes: list[dict] = []
    if VOTES_FILE.exists():
        with open(VOTES_FILE) as f:
            for line in f:
                votes.append(json.loads(line.strip()))

    bill_resp = supabase.table("parliament_bills").select("id,bill_number").execute()
    bill_lookup = {row["bill_number"]: row["id"] for row in (bill_resp.data or [])}

    stmt_stats = await upload_statements(supabase, statements, name_lookup, sitting_date_filter)
    votes_inserted = await upload_votes(supabase, votes, name_lookup, bill_lookup, sitting_date_filter)

    affected = [
        name_lookup[s["mp_name"]]["mp_id"]
        for s in statements
        if s.get("mp_name") in name_lookup
        and (not sitting_date_filter or s["sitting_date"] == sitting_date_filter)
    ]
    if affected:
        _update_mp_scores(supabase, affected)

    sitting_dates = list({s["sitting_date"] for s in statements})
    if sitting_date_filter:
        sitting_dates = [d for d in sitting_dates if d == sitting_date_filter]
    _mark_sitting_ingested(supabase, sitting_dates)

    log.info(
        "upload_pipeline_complete",
        sittings_processed=len(sitting_dates),
        name_lookup_size=len(name_lookup),
        votes_inserted=votes_inserted,
        **stmt_stats,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sitting-date", type=str, default=None,
                         help="Process only a specific date (YYYY-MM-DD)")
    args = parser.parse_args()
    asyncio.run(main(args.sitting_date))
