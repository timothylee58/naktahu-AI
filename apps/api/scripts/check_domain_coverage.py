#!/usr/bin/env python3
"""Domain-coverage report: registered sources vs. actual document_chunks
content vs. eval-dataset coverage, per canonical domain — the three axes
cross-checking each other, not one script re-verifying what another
already covers:

  1. scripts/sources.py     — do we have a URL to ingest for this domain?
  2. document_chunks (live) — did an ingest run actually put content there?
  3. evals/*.jsonl           — do we have a test query for this domain?

check_sources.py answers a fourth, different question ("are the registered
URLs still alive?") and stays a separate script — that's a health check on
axis 1's data, not a fourth coverage axis.

Usage:
    python -m scripts.check_domain_coverage

Requires SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY to report axis 2 — without
them this still reports axes 1 and 3 (both are local/offline), just not
whether anything's actually been ingested. Never raises past main() — a
reporting tool must never crash the pipeline over its own unavailability
(Trap #4's degrade-gracefully spirit, applied to a standalone script the
same way deadline_monitor.py's subscription queries already do).

Exit code: 1 if any domain has sources registered but zero live chunks
(axis 1 without axis 2 — the specific gap this script exists to catch),
or zero eval coverage (axis 3 missing) — so a scheduled run actually
fails loudly instead of printing a report nobody reads. Missing axis 2
data entirely (no Supabase creds) does NOT fail the run — that's a
sandbox/environment limitation, not a coverage gap.

Canonical domain list duplicated here rather than imported from
app.agents.router_node — that module pulls in weave/llm_client at import
time (needs API keys just to load), which this lightweight reporting
script shouldn't require. Same duplication-with-a-comment pattern
scripts/ingest_feed.py already uses for its own copy (Trap #6: any change
to the canonical list touches every site in one PR, this is now one more).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_VALID_DOMAINS = (
    "government", "education", "legal", "finance", "healthcare", "epf",
    "tax", "business", "immigration", "culture", "parliament", "property",
    "welfare", "scam_check",
)

_EVALS_DIR = Path(__file__).parent.parent / "evals"


def _registered_source_counts() -> dict[str, int]:
    from scripts.sources import SOURCES
    counts: dict[str, int] = {d: 0 for d in _VALID_DOMAINS}
    for s in SOURCES:
        counts[s.domain] = counts.get(s.domain, 0) + 1
    return counts


def _eval_coverage() -> dict[str, int]:
    """Query count per domain across both eval datasets — answer_quality.jsonl
    tags its domain as `expected_topic`, language_accuracy.jsonl as `domain`
    (the two datasets predate a shared schema; reading both field names here
    rather than unifying them, since that's a larger change than this
    reporting script should make unprompted)."""
    counts: dict[str, int] = {d: 0 for d in _VALID_DOMAINS}
    for filename, key in (("answer_quality.jsonl", "expected_topic"), ("language_accuracy.jsonl", "domain")):
        path = _EVALS_DIR / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            domain = json.loads(line).get(key)
            if domain in counts:
                counts[domain] += 1
    return counts


def _chunk_counts(client) -> dict[str, dict]:
    """One row per domain: {count, newest_created_at}. Empty dict for a
    domain with zero rows — never fabricated as "0 rows, N/A date" if the
    query itself failed; that's a hard error, not a coverage gap."""
    result: dict[str, dict] = {}
    for domain in _VALID_DOMAINS:
        resp = (
            client.table("document_chunks")
            .select("created_at", count="exact")
            .eq("domain", domain)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        count = resp.count or 0
        newest = resp.data[0]["created_at"] if resp.data else None
        result[domain] = {"count": count, "newest_created_at": newest}
    return result


def _status_for(n_sources: int, n_chunks: int | None, n_evals: int) -> str:
    if n_sources == 0 and (n_chunks or 0) == 0:
        status = "NO SOURCES REGISTERED"
    elif n_sources > 0 and n_chunks == 0:
        status = "REGISTERED BUT NEVER INGESTED"
    elif n_sources == 0 and (n_chunks or 0) > 0:
        status = "content with no registered source (separate pipeline?)"
    else:
        status = "ok"
    if n_evals == 0:
        status += " | NO EVAL COVERAGE"
    return status


def main() -> int:
    source_counts = _registered_source_counts()
    eval_counts = _eval_coverage()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    chunks: dict[str, dict] | None = None
    if supabase_url and supabase_key:
        try:
            from supabase import create_client
            client = create_client(supabase_url, supabase_key)
            chunks = _chunk_counts(client)
        except Exception as exc:  # noqa: BLE001 — reporting tool must never crash the caller
            print(f"Could not query document_chunks (live-content axis skipped): {exc}\n")
    else:
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — live-content axis skipped.\n")

    print(f"{'domain':12s} {'sources':>8s} {'chunks':>8s}  {'evals':>6s}  {'newest chunk':>20s}  status")
    print("-" * 95)
    any_real_gap = False
    for domain in _VALID_DOMAINS:
        n_sources = source_counts[domain]
        n_evals = eval_counts[domain]
        n_chunks = chunks[domain]["count"] if chunks is not None else None
        newest = (chunks[domain]["newest_created_at"] if chunks is not None else None) or "—"
        status = _status_for(n_sources, n_chunks, n_evals)
        # Any of these three markers is a real, always-checkable gap —
        # "NO SOURCES REGISTERED" and "NO EVAL COVERAGE" don't need DB
        # access to know; "REGISTERED BUT NEVER INGESTED" can only appear
        # in `status` at all when chunks is available (n_chunks stays None,
        # not 0, without credentials — _status_for's `n_chunks == 0` check
        # is False for None, so that phrase is naturally unreachable then).
        # A single substring check here — not gated on `chunks is not
        # None` — used to silently miss "NO SOURCES REGISTERED" (visible
        # in the table, parliament's real case) while credentials were
        # unset, which is exactly the kind of table-says-one-thing-exit-
        # code-says-another bug this script exists to catch in OTHER data.
        if any(marker in status for marker in ("NO SOURCES REGISTERED", "REGISTERED BUT NEVER INGESTED", "NO EVAL COVERAGE")):
            any_real_gap = True
        n_chunks_display = n_chunks if n_chunks is not None else "—"
        print(f"{domain:12s} {n_sources:8d} {n_chunks_display:>8}  {n_evals:6d}  {newest:>20s}  {status}")

    return 1 if any_real_gap else 0


if __name__ == "__main__":
    raise SystemExit(main())
