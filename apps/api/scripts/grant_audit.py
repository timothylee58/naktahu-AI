#!/usr/bin/env python3
"""Read-only audit of the ``grant_database`` catalogue.

Reports what the Grant Finder and Grant Draft Generator actually have to work with:
row counts, stale or missing deadlines, how long since each row was verified, missing
amounts / documents / URLs, duplicate names, and which names the draft generator's
exact-match lookup would fail to find when typed by hand (case, spacing, partial name).

    python -m scripts.grant_audit
    python -m scripts.grant_audit --try "MDEC Digital Grant;MDAG"
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

STALE_VERIFY_DAYS = 90
COLUMNS = (
    "id,programme_name,agency,grant_type,amount_min_myr,amount_max_myr,application_deadline,"
    "deadline_is_rolling,is_active,application_url,source_url,last_verified,budget_year,"
    "eligible_sectors,required_documents"
)


def _d(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def audit(rows: list[dict[str, Any]], today: date) -> list[str]:
    """Pure: turn catalogue rows into report lines."""
    lines: list[str] = []
    active = [r for r in rows if r.get("is_active")]
    lines.append(f"rows: {len(rows)} total, {len(active)} active, {len(rows) - len(active)} inactive")
    lines.append("by agency (active): " + ", ".join(f"{a}={n}" for a, n in sorted(Counter(str(r.get('agency')) for r in active).items())))
    lines.append("by type (active): " + ", ".join(f"{a}={n}" for a, n in sorted(Counter(str(r.get('grant_type')) for r in active).items())))

    def bad(title: str, picked: list[dict[str, Any]]) -> None:
        lines.append(f"\n{title}: {len(picked)}")
        for r in picked:
            lines.append(f"  - {r.get('programme_name')} [{r.get('agency')}]")

    bad("active, fixed deadline already PAST", [r for r in active if not r.get("deadline_is_rolling") and (_d(r.get("application_deadline")) or date.max) < today])
    bad("active, not rolling and NO deadline", [r for r in active if not r.get("deadline_is_rolling") and not r.get("application_deadline")])
    bad(f"active, last_verified older than {STALE_VERIFY_DAYS} days or never", [r for r in active if (_d(r.get("last_verified")) is None) or (today - _d(r.get("last_verified"))).days > STALE_VERIFY_DAYS])  # type: ignore[arg-type]
    bad("active, no amount_min and no amount_max", [r for r in active if r.get("amount_min_myr") is None and r.get("amount_max_myr") is None])
    bad("active, no application_url", [r for r in active if not r.get("application_url")])
    bad("active, no required_documents", [r for r in active if not r.get("required_documents")])
    names = Counter(str(r.get("programme_name") or "").strip().lower() for r in rows)
    dupes = [n for n, c in names.items() if c > 1]
    lines.append(f"\nduplicate programme names (case-insensitive): {len(dupes)}" + "".join(f"\n  - {n}" for n in dupes))
    lines.append("\nprogramme names as stored (what an exact match must equal):")
    for r in sorted(rows, key=lambda x: str(x.get("programme_name"))):
        lines.append(f"  {'ok ' if r.get('is_active') else 'off'} {r.get('programme_name')!r}  deadline={r.get('application_deadline')} rolling={r.get('deadline_is_rolling')} verified={r.get('last_verified')}")
    return lines


def exact_match(rows: list[dict[str, Any]], typed: str) -> bool:
    return any(r.get("programme_name") == typed for r in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--try", dest="typed", default="", help="semicolon-separated names to test against the exact-match lookup")
    parser.add_argument("--runs", action="store_true", help="also count agent_sessions / agent_runs rows")
    args = parser.parse_args()

    from supabase import create_client

    from core.config import settings

    client = create_client(settings.supabase_url, settings.supabase_service_key)
    try:
        rows = list(client.table("grant_database").select(COLUMNS).execute().data or [])
    except Exception as exc:
        print(f"grant_database read FAILED: {type(exc).__name__}: {str(exc)[:300]}")
        return 1
    print("\n".join(audit(rows, datetime.now(timezone.utc).date())))
    if args.runs:
        for table in ("agent_sessions", "agent_runs"):
            try:
                res = client.table(table).select("id", count="exact").limit(1).execute()
                print(f"\n{table}: {res.count} rows")
            except Exception as exc:
                print(f"\n{table}: read FAILED {type(exc).__name__}: {str(exc)[:200]}")
        try:
            rows = client.table("agent_runs").select("agent_name").limit(1000).execute().data or []
            print("agent_runs by agent_name: " + (", ".join(f"{a}={n}" for a, n in sorted(Counter(r['agent_name'] for r in rows).items())) or "(none)"))
        except Exception as exc:
            print(f"agent_runs breakdown FAILED {type(exc).__name__}")
    for typed in [t.strip() for t in args.typed.split(";") if t.strip()]:
        print(f"\nexact-match lookup for {typed!r}: {'FOUND' if exact_match(rows, typed) else 'NOT FOUND'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
