#!/usr/bin/env python3
"""Nightly Deadline Monitor cron — scrape LHDN/EPF/SSM/SST sources, diff dates.

Run via Railway cron at 02:00 MYT (18:00 UTC):
  python scripts/agents/deadline_monitor.py

Alerts at 14/7/1 days before due_date (stdout log; wire WhatsApp/email in prod).
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import structlog

# apps/api root — works in Docker (/app) and local dev.
_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from core.config import settings  # noqa: E402

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

_DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"),
    re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b"),
    re.compile(
        r"\b(\d{1,2})\s+(Januari|Februari|Mac|April|Mei|Jun|Julai|Ogos|September|Oktober|November|Disember)\s+(\d{4})\b",
        re.IGNORECASE,
    ),
]

_BM_MONTHS = {
    "januari": 1, "februari": 2, "mac": 3, "april": 4, "mei": 5, "jun": 6,
    "julai": 7, "ogos": 8, "september": 9, "oktober": 10, "november": 11, "disember": 12,
}

_ALERT_DAYS = (14, 7, 1)


def _parse_dates(text: str) -> list[date]:
    found: list[date] = []
    for m in _DATE_PATTERNS[0].finditer(text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            found.append(date(y, mo, d))
        except ValueError:
            pass
    for m in _DATE_PATTERNS[1].finditer(text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            found.append(date(y, mo, d))
        except ValueError:
            pass
    for m in _DATE_PATTERNS[2].finditer(text):
        d = int(m.group(1))
        mo = _BM_MONTHS.get(m.group(2).lower(), 0)
        y = int(m.group(3))
        if mo:
            try:
                found.append(date(y, mo, d))
            except ValueError:
                pass
    return found


def _fetch_url(url: str) -> str:
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "NakTahu-DeadlineMonitor/1.0"})
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPError as exc:
        log.warning("fetch_failed", url=url, error=str(exc))
        return ""


def _load_schedule(supabase) -> list[dict]:
    res = supabase.table("deadline_schedule").select("*").execute()
    return res.data or []


def _send_alert(entry: dict, days_left: int) -> None:
    log.info(
        "deadline_alert",
        domain=entry.get("domain"),
        name=entry.get("deadline_name"),
        due_date=str(entry.get("due_date")),
        days_left=days_left,
        source_url=entry.get("source_url"),
    )


def main() -> None:
    from supabase import create_client

    sb = create_client(settings.supabase_url, settings.supabase_service_key)
    today = date.today()
    entries = _load_schedule(sb)

    for entry in entries:
        due = entry.get("due_date")
        if isinstance(due, str):
            due = date.fromisoformat(due)
        if not due:
            continue

        for alert_day in _ALERT_DAYS:
            if due - today == timedelta(days=alert_day):
                _send_alert(entry, alert_day)

        url = entry.get("source_url") or ""
        if not url:
            continue
        html = _fetch_url(url)
        if not html:
            continue
        extracted = _parse_dates(html[:50_000])
        if extracted and due not in extracted:
            nearest = min(extracted, key=lambda d: abs((d - due).days))
            if abs((nearest - due).days) <= 7:
                log.info(
                    "deadline_date_drift",
                    name=entry.get("deadline_name"),
                    stored=str(due),
                    scraped=str(nearest),
                    url=url,
                )
                sb.table("deadline_schedule").update({
                    "due_date": nearest.isoformat(),
                    "last_verified": datetime.now(timezone.utc).isoformat(),
                }).eq("id", entry["id"]).execute()

    log.info("deadline_monitor_complete", checked=len(entries))


if __name__ == "__main__":
    main()
