#!/usr/bin/env python3
"""Nightly grant refresh — re-check every active grant against its agency's site.

The Eligibility Agent already verifies a user's top matches live (Tavily), but
that costs credits and latency per query and nothing re-checks the grants nobody
asked about. This job runs the SAME classifier (app.agents.eligibility_agent.
verification) over every active row of ``grant_database`` once a night and
reports what moved.

What it writes, and what it never writes
-----------------------------------------
  confirmed    the agency page states the deadline we hold
               -> sets ``last_verified`` to today (live mode only)
  changed      the page states a DIFFERENT deadline
  closed       the page says applications are closed
               -> REPORTED ONLY (annotation + step summary + JSON). The database
                  is never edited: a changed or closed grant is for a human to
                  confirm against the agency, then update.
  no_signal / unavailable
               -> nothing. We only stamp ``last_verified`` on positive evidence.

It only ever updates the single column ``last_verified``, and only for grants
whose status is ``confirmed``. It never touches ``application_deadline``
(migration 023 mirrors that column into deadline_schedule, so a bad write there
would fan out into user-facing deadline alerts).

Modes: dry-run (default; reads and reports, writes nothing) and ``--live``. The
workflow (.github/workflows/grant-refresh.yml) runs live on a schedule only when
the repository variable GRANT_REFRESH_LIVE is 'true'.

Exit codes: 0 ok (changes found are warnings, not failures); 1 infrastructure
failure (database unreachable or unconfigured, or every check failed — e.g. an
invalid or exhausted Tavily key — so a silently dead job cannot look green).

Usage (from apps/api):
    TAVILY_API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \\
        python scripts/agents/grant_refresh.py [--live] [--report-json out.json] [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog

# apps/api root — works in Docker (/app) and local dev (same pattern as deadline_monitor).
_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.agents.eligibility_agent import verification as ver  # noqa: E402
from core.config import settings  # noqa: E402

log = structlog.get_logger(__name__)

GRANT_COLUMNS = (
    "id,programme_name,agency,application_url,source_url,"
    "application_deadline,deadline_is_rolling,last_verified"
)
_CONCURRENCY = 3

# actions
STAMPED = "stamped"
WOULD_STAMP = "would_stamp"
NEEDS_REVIEW = "needs_review"
NONE = "none"


@dataclass
class Outcome:
    grant_id: str
    programme: str
    agency: str
    status: str
    reason: Optional[str]
    db_deadline: Optional[str]
    found_deadline: Optional[str]
    source_url: Optional[str]
    action: str


def action_for(status: str, *, live: bool) -> str:
    """The single place that decides what a verification status is allowed to do."""
    if status == ver.CONFIRMED:
        return STAMPED if live else WOULD_STAMP
    if status in (ver.CHANGED, ver.CLOSED):
        return NEEDS_REVIEW
    return NONE


def _clean(text: Any) -> str:
    """One line, no GitHub workflow-command syntax (names come from the database)."""
    return " ".join(str(text or "").split()).replace("::", ": :")


async def check_all(
    grants: list[dict[str, Any]], client: Any, *, live: bool, today: date
) -> list[Outcome]:
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _one(grant: dict[str, Any]) -> Outcome:
        async with sem:
            record = await ver.verify_grant(grant, client, today=today, use_cache=False)
        status = record.get("status", ver.UNAVAILABLE)
        return Outcome(
            grant_id=str(grant.get("id") or ""),
            programme=str(grant.get("programme_name") or ""),
            agency=str(grant.get("agency") or ""),
            status=status,
            reason=record.get("reason"),
            db_deadline=record.get("db_deadline") or (str(grant["application_deadline"])[:10] if grant.get("application_deadline") else None),
            found_deadline=record.get("found_deadline"),
            source_url=record.get("source_url"),
            action=action_for(status, live=live),
        )

    return list(await asyncio.gather(*(_one(g) for g in grants)))


def apply_stamps(supabase: Any, outcomes: list[Outcome], today: date) -> int:
    """Write ``last_verified`` for confirmed grants. Returns how many succeeded.

    The payload is exactly {"last_verified": today} — see the module docstring
    for why no other column is ever written here.
    """
    done = 0
    for o in outcomes:
        if o.action != STAMPED or not o.grant_id:
            continue
        try:
            supabase.table("grant_database").update({"last_verified": today.isoformat()}).eq("id", o.grant_id).execute()
            done += 1
        except Exception as exc:  # one bad row must not stop the rest
            log.warning("grant_stamp_failed", programme=o.programme[:60], error=type(exc).__name__)
            o.action = NONE
    return done


def render_summary(outcomes: list[Outcome], *, live: bool, today: date) -> str:
    counts: dict[str, int] = {}
    for o in outcomes:
        counts[o.status] = counts.get(o.status, 0) + 1
    lines = [
        f"## Grant refresh — {today.isoformat()} ({'LIVE' if live else 'dry-run: nothing was written'})",
        "",
        f"Checked **{len(outcomes)}** active grants. "
        + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
        "",
    ]
    review = [o for o in outcomes if o.action == NEEDS_REVIEW]
    if review:
        lines += ["### Needs a human (the database was NOT changed)", "",
                  "| Programme | Status | Our record | Agency site says | Source |", "|---|---|---|---|---|"]
        for o in review:
            src = f"[link]({o.source_url})" if o.source_url else "—"
            lines.append(f"| {_clean(o.programme)} | {o.status} | {o.db_deadline or '—'} | {o.found_deadline or '—'} | {src} |")
        lines.append("")
    stamped = sum(o.action in (STAMPED, WOULD_STAMP) for o in outcomes)
    lines.append(f"{'Stamped' if live else 'Would stamp'} `last_verified` on **{stamped}** confirmed grants.")
    unavailable = [o for o in outcomes if o.status == ver.UNAVAILABLE]
    if unavailable:
        reasons: dict[str, int] = {}
        for o in unavailable:
            reasons[o.reason or "unknown"] = reasons.get(o.reason or "unknown", 0) + 1
        lines.append("Not checked: " + ", ".join(f"{k}: {v}" for k, v in sorted(reasons.items())) + ".")
    return "\n".join(lines) + "\n"


def all_checks_failed(outcomes: list[Outcome]) -> bool:
    """True when every check died in the search itself (bad/exhausted key, outage)."""
    return bool(outcomes) and all(o.reason == "search_failed" for o in outcomes)


def load_grants(supabase: Any, limit: Optional[int] = None) -> list[dict[str, Any]]:
    query = supabase.table("grant_database").select(GRANT_COLUMNS).eq("is_active", True)
    if limit:
        query = query.limit(limit)
    return list(query.execute().data or [])


def _supabase_configured() -> bool:
    url = settings.supabase_url or ""
    return bool(url) and not url.startswith("http://localhost") and settings.supabase_service_key != "dev-service-role-key"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Nightly grant refresh")
    parser.add_argument("--live", action="store_true", help="stamp last_verified on confirmed grants (default: dry-run)")
    parser.add_argument("--report-json", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    if not settings.tavily_api_key:
        print("::notice title=Grant refresh skipped::TAVILY_API_KEY is not set; nothing was checked.")
        return 0
    if not _supabase_configured():
        print("::error title=Grant refresh::SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not configured.")
        return 1

    from supabase import create_client

    today = datetime.now(timezone.utc).date()
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_service_key)
        grants = load_grants(supabase, args.limit)
    except Exception as exc:
        print(f"::error title=Grant refresh::could not read grant_database ({type(exc).__name__}).")
        return 1

    client = ver.make_client()
    outcomes = asyncio.run(check_all(grants, client, live=args.live, today=today))

    stamped = apply_stamps(supabase, outcomes, today) if args.live else 0
    summary = render_summary(outcomes, live=args.live, today=today)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary)
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps([asdict(o) for o in outcomes], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    for o in outcomes:
        if o.action == NEEDS_REVIEW:
            print(
                f"::warning title=Grant {o.status}::{_clean(o.programme)} — our record {o.db_deadline or 'none'}, "
                f"agency site says {o.found_deadline or o.status}. {o.source_url or ''}"
            )
    print(f"stamped={stamped} checked={len(outcomes)}")

    if all_checks_failed(outcomes):
        print("::error title=Grant refresh::every check failed in the search step (invalid or exhausted TAVILY_API_KEY, or an outage).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
