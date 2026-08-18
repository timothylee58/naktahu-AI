#!/usr/bin/env python3
"""Domain-coverage report: registered sources vs. actual document_chunks
content, per canonical domain.

check_sources.py answers "are the registered URLs still alive?". This
answers the different, higher-level question the ingest-sources.yml
workflow's dynamic `SOURCES` loop can't: after a run, did every domain that
HAS registered sources actually END UP with real rows in document_chunks —
and separately, which domains have zero sources registered at all, so
there's nothing a scheduled run could ever ingest for them no matter how
often it runs.

Usage:
    python -m scripts.check_domain_coverage

Requires SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (same as any other script
that reads live data) — degrades to a clear message and exit 0 rather than
a stack trace if they're unset or the connection fails, since this is a
reporting tool, not something that should ever block a pipeline over its
own unavailability (Trap #4's degrade-gracefully spirit, applied to a
standalone script the same way deadline_monitor.py's subscription queries
already do).

Canonical domain list duplicated here rather than imported from
app.agents.router_node — that module pulls in weave/llm_client at import
time (needs API keys just to load), which this lightweight reporting
script shouldn't require. Same duplication-with-a-comment pattern
scripts/ingest_feed.py already uses for its own copy (Trap #6: any change
to the canonical list touches every site in one PR, this is now one more).
"""
from __future__ import annotations

import os

_VALID_DOMAINS = (
    "government", "education", "legal", "finance", "healthcare", "epf",
    "tax", "business", "immigration", "culture", "parliament", "property",
    "welfare",
)


def _registered_source_counts() -> dict[str, int]:
    from scripts.sources import SOURCES
    counts: dict[str, int] = {d: 0 for d in _VALID_DOMAINS}
    for s in SOURCES:
        counts[s.domain] = counts.get(s.domain, 0) + 1
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


def main() -> None:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — cannot report live "
              "document_chunks coverage. Registered-source counts only:\n")
        source_counts = _registered_source_counts()
        for domain in _VALID_DOMAINS:
            print(f"  {domain:12s} {source_counts[domain]} source(s) registered")
        return

    try:
        from supabase import create_client
        client = create_client(supabase_url, supabase_key)
        source_counts = _registered_source_counts()
        chunks = _chunk_counts(client)
    except Exception as exc:  # noqa: BLE001 — reporting tool must never crash the caller
        print(f"Could not query document_chunks: {exc}")
        return

    print(f"{'domain':12s} {'sources':>8s} {'chunks':>8s}  {'newest chunk':>20s}  status")
    print("-" * 80)
    for domain in _VALID_DOMAINS:
        n_sources = source_counts[domain]
        n_chunks = chunks[domain]["count"]
        newest = chunks[domain]["newest_created_at"] or "—"
        if n_sources == 0 and n_chunks == 0:
            status = "NO SOURCES REGISTERED — nothing to ingest"
        elif n_sources > 0 and n_chunks == 0:
            status = "REGISTERED BUT NEVER INGESTED — run ingest_feed for this domain"
        elif n_sources == 0 and n_chunks > 0:
            status = "has content, no registered source (fed by a separate pipeline?)"
        else:
            status = "ok"
        print(f"{domain:12s} {n_sources:8d} {n_chunks:8d}  {newest:>20s}  {status}")


if __name__ == "__main__":
    main()
