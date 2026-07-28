"""tests/test_deadline_monitor.py

Unit tests for the extended Deadline Monitor cron script: alert-day windows,
domain-wide Pro-plan subscription delivery, dedup via deadline_alert_sends,
and degrade-gracefully behaviour when send_email fails.

Supabase is mocked as a plain MagicMock chain (the script uses the SYNC
supabase-py client, not the async one used elsewhere in this repo's
FastAPI routers/agent nodes — see scripts/agents/deadline_monitor.py's
`create_client` usage). send_email (app.agents.tools.send_email) is mocked
directly so no real network call happens.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import scripts.agents.deadline_monitor as deadline_monitor


ENTRY = {
    "id": "dl-1",
    "domain": "business",
    "deadline_name": "CIP Spark",
    "due_date": "2026-08-27",
    "source_url": "https://cradle.com.my/programmes",
}

PRO_SUB = {"id": "sub-pro", "user_id": "user-pro", "domain": "business"}
FREE_SUB = {"id": "sub-free", "user_id": "user-free", "domain": "business"}


def _admin_user(plan: str, email: str | None = "user@example.com") -> MagicMock:
    user = MagicMock()
    user.app_metadata = {"plan": plan} if plan else {}
    user.email = email
    admin_user = MagicMock()
    admin_user.user = user
    return admin_user


class TestAlertDayWindow:
    def test_alert_days_includes_30(self):
        assert deadline_monitor._ALERT_DAYS == (30, 14, 7, 1)


class TestSubscriptionDelivery:
    @pytest.mark.asyncio
    async def test_subscribed_pro_user_is_emailed(self):
        sb = MagicMock()

        def _table(name: str) -> MagicMock:
            chain = MagicMock()
            if name == "deadline_alert_subscriptions":
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[PRO_SUB]
                )
            elif name == "deadline_alert_sends":
                chain.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[]
                )
                chain.insert.return_value.execute.return_value = MagicMock(data=[{}])
            return chain

        sb.table.side_effect = _table
        sb.auth.admin.get_user_by_id.return_value = _admin_user("pro")

        with patch.object(deadline_monitor, "send_email", new=AsyncMock(return_value=True)) as mock_send:
            await deadline_monitor._dispatch_alert(sb, ENTRY, 14)

        mock_send.assert_awaited_once()
        assert mock_send.await_args.kwargs["to"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_subscribed_free_user_is_not_emailed(self):
        sb = MagicMock()

        def _table(name: str) -> MagicMock:
            chain = MagicMock()
            if name == "deadline_alert_subscriptions":
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[FREE_SUB]
                )
            return chain

        sb.table.side_effect = _table
        sb.auth.admin.get_user_by_id.return_value = _admin_user("free")

        with patch.object(deadline_monitor, "send_email", new=AsyncMock(return_value=True)) as mock_send:
            await deadline_monitor._dispatch_alert(sb, ENTRY, 14)

        mock_send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_domain_wide_match_uses_entry_domain(self):
        """The subscription lookup must be keyed off entry['domain'], not a
        per-deadline id — this is the whole point of domain-wide subscriptions."""
        sb = MagicMock()
        seen_domains: list[str] = []

        def _table(name: str) -> MagicMock:
            chain = MagicMock()
            if name == "deadline_alert_subscriptions":
                def _eq(field, value):
                    if field == "domain":
                        seen_domains.append(value)
                    inner = MagicMock()
                    inner.execute.return_value = MagicMock(data=[])
                    return inner
                chain.select.return_value.eq.side_effect = _eq
            return chain

        sb.table.side_effect = _table

        with patch.object(deadline_monitor, "send_email", new=AsyncMock(return_value=True)):
            await deadline_monitor._dispatch_alert(sb, ENTRY, 14)

        assert seen_domains == ["business"]


class TestDedup:
    @pytest.mark.asyncio
    async def test_already_sent_alert_is_skipped(self):
        sb = MagicMock()

        def _table(name: str) -> MagicMock:
            chain = MagicMock()
            if name == "deadline_alert_subscriptions":
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[PRO_SUB]
                )
            elif name == "deadline_alert_sends":
                chain.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"subscription_id": "sub-pro"}]
                )
            return chain

        sb.table.side_effect = _table
        sb.auth.admin.get_user_by_id.return_value = _admin_user("pro")

        with patch.object(deadline_monitor, "send_email", new=AsyncMock(return_value=True)) as mock_send:
            await deadline_monitor._dispatch_alert(sb, ENTRY, 14)

        mock_send.assert_not_awaited()


class TestDegradeGracefully:
    @pytest.mark.asyncio
    async def test_send_email_raises_does_not_crash_and_no_dedup_row(self):
        sb = MagicMock()
        insert_calls: list[dict] = []

        def _table(name: str) -> MagicMock:
            chain = MagicMock()
            if name == "deadline_alert_subscriptions":
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[PRO_SUB]
                )
            elif name == "deadline_alert_sends":
                chain.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[]
                )

                def _insert(payload):
                    insert_calls.append(payload)
                    inner = MagicMock()
                    inner.execute.return_value = MagicMock(data=[{}])
                    return inner

                chain.insert.side_effect = _insert
            return chain

        sb.table.side_effect = _table
        sb.auth.admin.get_user_by_id.return_value = _admin_user("pro")

        with patch.object(
            deadline_monitor, "send_email", new=AsyncMock(side_effect=RuntimeError("resend down"))
        ):
            await deadline_monitor._dispatch_alert(sb, ENTRY, 14)  # must not raise

        assert insert_calls == []

    @pytest.mark.asyncio
    async def test_send_email_returns_false_no_dedup_row_and_loop_continues(self):
        sb = MagicMock()
        insert_calls: list[dict] = []

        def _table(name: str) -> MagicMock:
            chain = MagicMock()
            if name == "deadline_alert_subscriptions":
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[PRO_SUB, {"id": "sub-pro-2", "user_id": "user-pro-2", "domain": "business"}]
                )
            elif name == "deadline_alert_sends":
                chain.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[]
                )

                def _insert(payload):
                    insert_calls.append(payload)
                    inner = MagicMock()
                    inner.execute.return_value = MagicMock(data=[{}])
                    return inner

                chain.insert.side_effect = _insert
            return chain

        sb.table.side_effect = _table
        sb.auth.admin.get_user_by_id.return_value = _admin_user("pro")

        with patch.object(deadline_monitor, "send_email", new=AsyncMock(return_value=False)) as mock_send:
            await deadline_monitor._dispatch_alert(sb, ENTRY, 14)

        # Both subscribers attempted (loop continued past the first "failure").
        assert mock_send.await_count == 2
        assert insert_calls == []

    def test_subscriptions_query_missing_table_returns_empty(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
            'relation "deadline_alert_subscriptions" does not exist'
        )
        assert deadline_monitor._load_subscriptions(sb, "business") == []
