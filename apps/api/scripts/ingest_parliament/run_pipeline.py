"""
scripts/ingest_parliament/run_pipeline.py

Master orchestrator for the full Hansard ingestion pipeline.
Runs all 4 steps in sequence:
  Step 1: fetch_hansard.py      - discover + download new PDFs
  Step 2: parse_hansard.py      - extract statements + votes
  Step 3: link_mp_profiles.py   - resolve MP names to profile IDs
  Step 4: upload_parliament.py  - embed + upload to Supabase

Intended cadence: weekly (Dewan Rakyat sits infrequently; a weekly cron is
generous). Like scripts/agents/deadline_monitor.py, the schedule itself is
NOT configured in this repo's code (no entry added to railway.toml) — it is
configured directly in the Railway dashboard's cron trigger UI, matching
that existing precedent. Suggested dashboard cron: 0 18 * * 0 (18:00 UTC =
02:00 MYT Sunday).

Usage:
  python -m scripts.ingest_parliament.run_pipeline              # full run
  python -m scripts.ingest_parliament.run_pipeline --year 2025  # specific year
  python -m scripts.ingest_parliament.run_pipeline --date 2025-07-07  # single sitting

Exit codes:
  0 - success
  1 - partial failure (some steps failed, see logs)
  2 - complete failure
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime

import structlog

log = structlog.get_logger(__name__)


async def run_step(name: str, coro) -> bool:
    """Run a pipeline step. Returns True on success."""
    start = time.monotonic()
    log.info("pipeline_step_start", step=name)
    try:
        await coro
        elapsed = time.monotonic() - start
        log.info("pipeline_step_complete", step=name, elapsed_s=round(elapsed, 1))
        return True
    except Exception as exc:
        log.error("pipeline_step_failed", step=name, error=str(exc))
        return False


async def main(year: int | None = None, sitting_date: str | None = None) -> int:
    """Run full pipeline. Returns exit code."""
    from scripts.ingest_parliament.fetch_hansard import main as fetch_main
    from scripts.ingest_parliament.link_mp_profiles import main as link_main
    from scripts.ingest_parliament.parse_hansard import process_manifest
    from scripts.ingest_parliament.upload_parliament import main as upload_main

    log.info(
        "parliament_pipeline_start",
        timestamp=datetime.utcnow().isoformat(),
        year=year,
        sitting_date=sitting_date,
    )

    results = {}

    results["fetch"] = await run_step(
        "fetch_hansard",
        fetch_main(year=year, dry_run=False),
    )

    results["parse"] = await run_step(
        "parse_hansard",
        asyncio.to_thread(process_manifest),
    )

    results["link"] = await run_step(
        "link_mp_profiles",
        asyncio.to_thread(link_main),
    )

    results["upload"] = await run_step(
        "upload_parliament",
        upload_main(sitting_date_filter=sitting_date),
    )

    failed = [step for step, ok in results.items() if not ok]

    if not failed:
        log.info("parliament_pipeline_success", steps=list(results.keys()))
        return 0
    elif len(failed) < len(results):
        log.warning("parliament_pipeline_partial", failed_steps=failed)
        return 1
    else:
        log.error("parliament_pipeline_complete_failure", failed_steps=failed)
        return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hansard ingestion pipeline")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--date", type=str, default=None,
                         help="Process single sitting date YYYY-MM-DD")
    args = parser.parse_args()
    exit_code = asyncio.run(main(args.year, args.date))
    sys.exit(exit_code)
