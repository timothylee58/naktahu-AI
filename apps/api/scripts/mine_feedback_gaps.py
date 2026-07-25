"""Mine negative feedback into eval candidates and content-gap reports.

CLAUDE.md's design intent for the feedback table (006_feedback.sql,
indexed on (rating, created_at)) is "mining negative feedback as eval
candidates" — this is that miner. It does not train anything; there is
no reward model or fine-tuning loop here. What it does:

1. Pull rating=-1 rows from Supabase.
2. For each, run the exact same keyword-overlap scoring analyst_node
   uses (_score_chunk) against that domain's real document_chunks, to
   tell apart two different failure classes:
     - CONTENT GAP: no chunk in the query's domain scores above the
       clarification threshold even with a perfect keyword match —
       the corpus is genuinely missing this topic. Needs ingestion.
     - RETRIEVAL/ROUTING ISSUE: relevant content exists and would score
       above threshold, but the pipeline didn't surface it — likely a
       classification or embedding-retrieval issue, not a content gap.
3. Emit a JSON eval-candidate file (evals/feedback_mined.jsonl) in the
   same shape as evals/answer_quality.jsonl, so confirmed content gaps
   become permanent regression coverage once ingested, and print a
   human-readable gap report.

Usage:
    python -m scripts.mine_feedback_gaps
    python -m scripts.mine_feedback_gaps --since 2026-07-01
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.agents.analyst_node import _score_chunk  # noqa: E402
from core.config import settings  # noqa: E402

load_dotenv()

_CLARIFICATION_THRESHOLD = 0.6


def _fetch_negative_feedback(supabase, since: str | None) -> list[dict]:
    q = supabase.table("feedback").select("query,domain,language,created_at").eq("rating", -1)
    if since:
        q = q.gte("created_at", since)
    res = q.order("created_at", desc=True).execute()
    return res.data or []


def _fetch_domain_chunks(supabase, domain: str) -> list[dict]:
    res = (
        supabase.table("document_chunks")
        .select("source_title,source_url,content")
        .eq("domain", domain)
        .execute()
    )
    return res.data or []


class _Chunk:
    """Minimal stand-in with just the fields _score_chunk reads.

    similarity is fixed at 0.0 — this script re-scores chunks already
    pulled from document_chunks directly, not via hybrid_search, so there
    is no real cosine/BM25 similarity to report. _relevance_signal takes
    max(overlap, similarity), so 0.0 just falls back to lexical overlap
    alone rather than fabricating a semantic score.
    """

    def __init__(self, source_url: str, source_title: str, content: str):
        self.source_url = source_url
        self.source_title = source_title
        self.content = content
        self.similarity = 0.0


def _best_score(query: str, chunks: list[dict]) -> tuple[float, str | None]:
    # Mirrors analyst_node's real confidence: average of the top 3 scored
    # chunks, not the single best one — a single-best approximation
    # understates confidence for domains with several corroborating
    # chunks and would misclassify genuinely-answerable queries (e.g.
    # tax, which has 9 chunks) as content gaps.
    scored = sorted(
        (
            (
                _score_chunk(
                    _Chunk(row.get("source_url") or "", row.get("source_title") or "", row.get("content") or ""),
                    query,
                ),
                row.get("source_title"),
            )
            for row in chunks
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    if not scored:
        return 0.0, None
    top3 = scored[:3]
    avg_score = sum(s for s, _ in top3) / len(top3)
    best_title = top3[0][1]
    return avg_score, best_title


def mine(since: str | None = None) -> list[dict]:
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    rows = _fetch_negative_feedback(supabase, since)
    if not rows:
        print("No negative feedback found.")
        return []

    domain_cache: dict[str, list[dict]] = {}
    findings: list[dict] = []

    for row in rows:
        query = row["query"]
        domain = row.get("domain") or "general"
        if domain not in domain_cache:
            domain_cache[domain] = _fetch_domain_chunks(supabase, domain)
        chunks = domain_cache[domain]

        best_score, best_title = _best_score(query, chunks)
        classification = "content_gap" if best_score < _CLARIFICATION_THRESHOLD else "retrieval_issue"

        findings.append(
            {
                "query": query,
                "domain": domain,
                "language": row.get("language"),
                "created_at": row.get("created_at"),
                "best_chunk_score": round(best_score, 4),
                "best_chunk_title": best_title,
                "classification": classification,
            }
        )

    return findings


def _print_report(findings: list[dict]) -> None:
    gaps = [f for f in findings if f["classification"] == "content_gap"]
    retrieval_issues = [f for f in findings if f["classification"] == "retrieval_issue"]

    print(f"\n{'=' * 70}")
    print(f"Mined {len(findings)} negative-feedback rows")
    print(f"  {len(gaps)} content gap(s) — corpus genuinely missing this topic")
    print(f"  {len(retrieval_issues)} retrieval/routing issue(s) — relevant content exists")
    print(f"{'=' * 70}\n")

    if gaps:
        print("CONTENT GAPS (need real ingestion — do not fabricate content):")
        for f in gaps:
            print(f"  [{f['domain']}] {f['query']!r} (best match: {f['best_chunk_score']})")
        print()

    if retrieval_issues:
        print("RETRIEVAL/ROUTING ISSUES (content exists, pipeline didn't surface it):")
        for f in retrieval_issues:
            print(f"  [{f['domain']}] {f['query']!r} -> best: {f['best_chunk_title']!r} ({f['best_chunk_score']})")
        print()


def _write_eval_candidates(findings: list[dict], out_path: Path) -> None:
    gaps = [f for f in findings if f["classification"] == "content_gap"]
    if not gaps:
        return
    with out_path.open("w", encoding="utf-8") as fh:
        for f in gaps:
            fh.write(
                json.dumps(
                    {
                        "query": f["query"],
                        "expected_topic": f["domain"],
                        "min_confidence": _CLARIFICATION_THRESHOLD,
                        "_source": "mined_negative_feedback",
                        "_mined_at": f["created_at"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"Wrote {len(gaps)} eval candidate(s) to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine negative feedback into eval candidates + gap report")
    parser.add_argument("--since", default=None, help="Only feedback at/after this ISO date")
    parser.add_argument(
        "--out",
        default=str(_API_ROOT / "evals" / "feedback_mined.jsonl"),
        help="Output path for mined eval candidates (content gaps only)",
    )
    args = parser.parse_args()

    findings = mine(since=args.since)
    if not findings:
        return
    _print_report(findings)
    _write_eval_candidates(findings, Path(args.out))


if __name__ == "__main__":
    main()
