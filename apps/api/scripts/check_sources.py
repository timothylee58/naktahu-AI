#!/usr/bin/env python3
"""Health-check every registered ingestion source — HEAD (falling back to
GET on 405) each URL in scripts/sources.py and report status.

Government sites restructure without warning; a source that was live when
registered can silently 404 months later, and the first sign would
otherwise be a scheduled ingest run quietly finding "nothing to ingest"
forever. This is meant to run on a schedule (see
.github/workflows/ingest-sources.yml, which runs this before the actual
ingest step) so rot gets caught as a loud CI failure, not a silent gap.

Usage:
    python -m scripts.check_sources
    python -m scripts.check_sources --source jkptg-home
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

from scripts.sources import SOURCES, SOURCES_BY_NAME, Source

_TIMEOUT_SECONDS = 15.0
_USER_AGENT = "NakTahu-AI-SourceHealthCheck/1.0 (+https://naktahu.my)"


async def _check_one(client: httpx.AsyncClient, source: Source) -> tuple[Source, int | None, str | None]:
    try:
        resp = await client.head(source.url, follow_redirects=True)
        if resp.status_code == 405:  # some servers reject HEAD outright
            resp = await client.get(source.url, follow_redirects=True)
        return source, resp.status_code, None
    except httpx.HTTPError as exc:
        return source, None, str(exc)


async def check_sources(sources: tuple[Source, ...]) -> bool:
    """Returns True if every source is healthy (2xx)."""
    headers = {"User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, headers=headers) as client:
        results = await asyncio.gather(*(_check_one(client, s) for s in sources))

    all_ok = True
    for source, status, error in results:
        if error is not None:
            all_ok = False
            print(f"FAIL  {source.name:45s} {source.url}  — {error}")
        elif status is None or status >= 400:
            all_ok = False
            print(f"FAIL  {source.name:45s} {source.url}  — HTTP {status}")
        else:
            print(f"OK    {source.name:45s} {source.url}  — HTTP {status}")

    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Health-check registered ingestion sources")
    parser.add_argument("--source", choices=sorted(SOURCES_BY_NAME), help="Check a single source (default: all)")
    args = parser.parse_args()

    targets = (SOURCES_BY_NAME[args.source],) if args.source else SOURCES
    ok = asyncio.run(check_sources(targets))

    print(f"\n{'='*60}")
    print(f"{sum(1 for _ in targets)} source(s) checked — {'all healthy' if ok else 'FAILURES ABOVE'}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
