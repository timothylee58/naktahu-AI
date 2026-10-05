"""Review "new chunk replaces old chunk" candidates queued by ingest_feed.py.

ingest_feed.py never retires a chunk on its own: for tax/EPF/immigration it
queues similar older chunks in supersede_candidates (migration 053). A human
checks each pair here.

Usage:
    python -m scripts.review_supersede --list
    python -m scripts.review_supersede --approve <candidate_id>
    python -m scripts.review_supersede --reject <candidate_id>

Approval is date-aware (approve_supersede() in migration 053): if the new
rule already applies, the old chunk is marked superseded; if it starts in the
future, the old chunk's window is closed the day before, so the old rule
stays the answer until then and the new one shows as an upcoming change.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from core.config import settings  # noqa: E402

load_dotenv()

_CHUNK_COLUMNS = "id, source_title, source_url, domain, effective_date, effective_until, content"
_PREVIEW_CHARS = 160


def _preview(chunk: dict) -> str:
    window = f"{chunk.get('effective_date') or '?'} → {chunk.get('effective_until') or 'open'}"
    text = " ".join((chunk.get("content") or "").split())[:_PREVIEW_CHARS]
    return f"{chunk.get('source_title')!r} [{window}]\n      {chunk.get('source_url')}\n      {text}"


def list_pending(supabase) -> int:
    res = (
        supabase.table("supersede_candidates")
        .select("id, new_chunk_id, old_chunk_id, similarity, created_at")
        .eq("status", "pending")
        .order("created_at")
        .execute()
    )
    candidates = res.data or []
    if not candidates:
        print("No pending supersede candidates.")
        return 0
    ids = list({c["new_chunk_id"] for c in candidates} | {c["old_chunk_id"] for c in candidates})
    chunks = {
        row["id"]: row
        for row in (supabase.table("document_chunks").select(_CHUNK_COLUMNS).in_("id", ids).execute().data or [])
    }
    for c in candidates:
        print(f"\n{c['id']}  (similarity {float(c['similarity']):.2f})")
        print(f"  NEW  {_preview(chunks.get(c['new_chunk_id'], {}))}")
        print(f"  OLD  {_preview(chunks.get(c['old_chunk_id'], {}))}")
    print(f"\n{len(candidates)} pending. Approve with --approve <id>, reject with --reject <id>.")
    return len(candidates)


def approve(supabase, candidate_id: str) -> str:
    outcome = supabase.rpc("approve_supersede", {"candidate_id": candidate_id}).execute().data
    meaning = {
        "superseded": "old chunk marked superseded (new rule already in force)",
        "window_closed": "old chunk's window closed the day before the new rule starts",
    }
    print(f"Approved {candidate_id}: {meaning.get(outcome, outcome)}")
    return str(outcome)


def reject(supabase, candidate_id: str) -> None:
    supabase.rpc("reject_supersede", {"candidate_id": candidate_id}).execute()
    print(f"Rejected {candidate_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Review supersede candidates queued by ingest_feed.py")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Show pending candidate pairs")
    group.add_argument("--approve", metavar="ID", help="Approve a candidate pair")
    group.add_argument("--reject", metavar="ID", help="Reject a candidate pair")
    args = parser.parse_args()

    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    if args.list:
        list_pending(supabase)
    elif args.approve:
        approve(supabase, args.approve)
    else:
        reject(supabase, args.reject)


if __name__ == "__main__":
    main()
