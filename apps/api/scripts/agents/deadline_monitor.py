#!/usr/bin/env python3
"""Nightly Deadline Monitor cron — scrape LHDN/EPF/SSM/SST sources, diff dates,
and notify Pro-plan subscribers approaching deadlines. Two delivery channels
as of migration 039: email (unconditional, at the 30/14/7/1-day alert
windows) and calendar push (Google/Microsoft, for whoever has connected —
runs every night regardless of alert window, since a connected calendar's
job is to always reflect the current due date, not just fire at specific
countdown thresholds).

Run via Railway cron at 02:00 MYT (18:00 UTC):
  python scripts/agents/deadline_monitor.py

Alerts at 30/14/7/1 days before due_date. Delivery is domain-wide: a user
subscribes to a domain (deadline_alert_subscriptions) and is emailed for
every deadline_schedule row in that domain, gated to the pro plan or above.
Dedup is enforced by the deadline_alert_sends ledger (PK-based, no
read-then-write race). Until migration 023 is applied, the subscription/
dedup queries below degrade to no-ops (empty subscriber list) rather than
crashing the cron run — Trap #5/#4 spirit applied to a standalone script.
Calendar push (migration 039) degrades the same way if its tables aren't
applied yet, or if a user's OAuth client isn't configured — see
services/calendar_sync.py's module docstring.
"""
from __future__ import annotations

import asyncio
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

from app.agents.tools import send_email  # noqa: E402
from core.config import settings  # noqa: E402
from middleware.plan_gate import _PLAN_RANK  # noqa: E402

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

_ALERT_DAYS = (30, 14, 7, 1)

# Minimum plan rank required to receive email alerts (Trap #6-adjacent: this
# imports the canonical _PLAN_RANK from middleware/plan_gate.py rather than
# duplicating it, since scripts/ is inside the same Python package as the
# rest of apps/api).
_MIN_ALERT_PLAN = "pro"


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


def _load_subscriptions(supabase, domain: str) -> list[dict]:
    """Domain-wide Pro-plan subscribers for `domain`. Returns [] rather than
    raising if deadline_alert_subscriptions doesn't exist yet (migration 023
    not applied) — never crash the cron run over a missing table (Trap #5)."""
    try:
        res = (
            supabase.table("deadline_alert_subscriptions")
            .select("*")
            .eq("domain", domain)
            .execute()
        )
        return res.data or []
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the cron run
        log.warning("deadline_alert_subscriptions_query_failed", domain=domain, error=str(exc))
        return []


def _already_sent(supabase, subscription_id: str, deadline_schedule_id: str, alert_day: int) -> bool:
    try:
        res = (
            supabase.table("deadline_alert_sends")
            .select("subscription_id")
            .eq("subscription_id", subscription_id)
            .eq("deadline_schedule_id", deadline_schedule_id)
            .eq("alert_day", alert_day)
            .execute()
        )
        return bool(res.data)
    except Exception as exc:  # noqa: BLE001
        log.warning("deadline_alert_sends_query_failed", error=str(exc))
        return False


def _record_sent(supabase, subscription_id: str, deadline_schedule_id: str, alert_day: int) -> None:
    try:
        supabase.table("deadline_alert_sends").insert(
            {
                "subscription_id": subscription_id,
                "deadline_schedule_id": deadline_schedule_id,
                "alert_day": alert_day,
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        log.warning("deadline_alert_sends_insert_failed", error=str(exc))


def _resolve_user_plan(supabase, user_id: str) -> tuple[str, str | None]:
    """Mirror services/auth.py: plan lives in app_metadata.plan (Supabase
    Auth JWT claim), and no separate plan/subscriptions table exists. The
    service-role admin API surfaces the same key as `app_metadata` on the
    User object, so this reads app_metadata.get("plan") directly — no
    duplicated plan store, no JWT to decode in a standalone script context.
    Missing/null plan is treated as 'free'."""
    try:
        admin_user = supabase.auth.admin.get_user_by_id(user_id)
        user = getattr(admin_user, "user", admin_user)
        app_metadata = getattr(user, "app_metadata", None) or {}
        plan = app_metadata.get("plan") or "free"
        email = getattr(user, "email", None)
        return plan, email
    except Exception as exc:  # noqa: BLE001
        log.warning("resolve_user_plan_failed", user_id=user_id, error=str(exc))
        return "free", None


async def _dispatch_alert(supabase, entry: dict, alert_day: int) -> None:
    """Email every Pro+ subscriber of entry['domain'] about this deadline,
    skipping alerts already recorded in deadline_alert_sends. One user's
    email failure must not stop the others (or the whole cron run)."""
    domain = entry.get("domain")
    deadline_schedule_id = entry.get("id")
    subscriptions = _load_subscriptions(supabase, domain)

    for sub in subscriptions:
        user_id = sub.get("user_id")
        subscription_id = sub.get("id")
        plan, email = _resolve_user_plan(supabase, user_id)
        if _PLAN_RANK.get(plan, 0) < _PLAN_RANK.get(_MIN_ALERT_PLAN, 0):
            continue
        if not email:
            log.warning("deadline_alert_no_email", user_id=user_id)
            continue
        if _already_sent(supabase, subscription_id, deadline_schedule_id, alert_day):
            continue

        subject = f"[NakTahu] {entry.get('deadline_name')} — {alert_day} day(s) left"
        html_body = (
            f"<p>Reminder: <strong>{entry.get('deadline_name')}</strong> "
            f"({domain}) is due on {entry.get('due_date')} — "
            f"{alert_day} day(s) from now.</p>"
            f"<p>Peringatan: tarikh akhir tersebut hampir tiba.</p>"
            f"<p>Source: <a href=\"{entry.get('source_url')}\">{entry.get('source_url')}</a></p>"
        )

        try:
            sent = await send_email(to=email, subject=subject, html_body=html_body)
        except Exception as exc:  # noqa: BLE001 - one user's failure must not kill the run
            log.error("deadline_alert_email_error", user_id=user_id, error=str(exc))
            continue

        if sent:
            _record_sent(supabase, subscription_id, deadline_schedule_id, alert_day)
        else:
            log.info("deadline_alert_email_not_sent", user_id=user_id, reason="send_email_returned_false")


async def _dispatch_all_alerts(supabase, due_alerts: list[tuple[dict, int]]) -> None:
    for entry, alert_day in due_alerts:
        await _dispatch_alert(supabase, entry, alert_day)


def _load_calendar_connections(supabase, user_ids: set[str]) -> list[dict]:
    """Every connected Google/Microsoft calendar for the given users.
    Returns [] (not a crash) if migration 039's table doesn't exist yet."""
    if not user_ids:
        return []
    try:
        res = (
            supabase.table("calendar_connections")
            .select("*")
            .in_("user_id", list(user_ids))
            .execute()
        )
        return res.data or []
    except Exception as exc:  # noqa: BLE001
        log.warning("calendar_connections_query_failed", error=str(exc))
        return []


async def _dispatch_calendar_sync(supabase, entries: list[dict]) -> None:
    """Push every deadline to every connected calendar for a subscriber of
    that domain — same Pro-plan gate as email (calendar sync is a richer
    delivery channel for the same feature, not a free-tier bypass of it),
    same domain-wide subscription list (deadline_alert_subscriptions).
    Runs for ALL entries, not just alert-day ones: a connected calendar
    should always show the current due date.
    """
    from services.calendar_sync import sync_deadline_to_connection

    entries_by_domain: dict[str, list[dict]] = {}
    for entry in entries:
        entries_by_domain.setdefault(entry.get("domain"), []).append(entry)

    for domain, domain_entries in entries_by_domain.items():
        subscriptions = _load_subscriptions(supabase, domain)
        if not subscriptions:
            continue

        subscriber_user_ids = set()
        for sub in subscriptions:
            plan, _ = _resolve_user_plan(supabase, sub.get("user_id"))
            if _PLAN_RANK.get(plan, 0) >= _PLAN_RANK.get(_MIN_ALERT_PLAN, 0):
                subscriber_user_ids.add(sub.get("user_id"))
        if not subscriber_user_ids:
            continue

        connections = _load_calendar_connections(supabase, subscriber_user_ids)
        for connection in connections:
            for entry in domain_entries:
                await sync_deadline_to_connection(supabase, connection, entry)


def main() -> None:
    from supabase import create_client

    sb = create_client(settings.supabase_url, settings.supabase_service_key)
    today = date.today()
    entries = _load_schedule(sb)
    due_alerts: list[tuple[dict, int]] = []

    for entry in entries:
        due = entry.get("due_date")
        if isinstance(due, str):
            due = date.fromisoformat(due)
        if not due:
            continue

        for alert_day in _ALERT_DAYS:
            if due - today == timedelta(days=alert_day):
                _send_alert(entry, alert_day)
                due_alerts.append((entry, alert_day))

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
                # Keep this run's in-memory copy in sync with the DB write
                # above — calendar push below reads `entries` directly, and
                # must push the corrected date, not the stale one it was
                # loaded with at the top of this function.
                entry["due_date"] = nearest.isoformat()

    async def _run_notifications() -> None:
        if due_alerts:
            await _dispatch_all_alerts(sb, due_alerts)
        await _dispatch_calendar_sync(sb, entries)

    asyncio.run(_run_notifications())

    log.info("deadline_monitor_complete", checked=len(entries), alerts_due=len(due_alerts))


if __name__ == "__main__":
    main()
