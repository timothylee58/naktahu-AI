"""Tests for the nightly grant refresh job (scripts/agents/grant_refresh.py)."""
from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import scripts.agents.grant_refresh as gr
from app.agents.eligibility_agent import verification as ver

TODAY = date(2026, 10, 8)


def _grant(i: int = 1, **over: Any) -> dict[str, Any]:
    base = {
        "id": f"g{i}",
        "programme_name": f"Grant {i}",
        "agency": "MDEC",
        "application_url": "https://www.mdec.my/apply",
        "source_url": None,
        "application_deadline": "2026-12-31",
        "deadline_is_rolling": False,
        "last_verified": "2026-01-01",
    }
    base.update(over)
    return base


def _client(content: str | Exception, url: str = "https://mdec.my/mdag") -> MagicMock:
    c = MagicMock()
    if isinstance(content, Exception):
        c.search = AsyncMock(side_effect=content)
    else:
        c.search = AsyncMock(return_value={"results": [{"url": url, "content": content}]})
    return c


def _supabase() -> MagicMock:
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    return sb


# ── what each status may do ──────────────────────────────────────────────────

@pytest.mark.parametrize(
    "status,live,expected",
    [
        (ver.CONFIRMED, True, gr.STAMPED),
        (ver.CONFIRMED, False, gr.WOULD_STAMP),
        (ver.CHANGED, True, gr.NEEDS_REVIEW),
        (ver.CHANGED, False, gr.NEEDS_REVIEW),
        (ver.CLOSED, True, gr.NEEDS_REVIEW),
        (ver.NO_SIGNAL, True, gr.NONE),
        (ver.UNAVAILABLE, True, gr.NONE),
    ],
)
def test_action_for_each_status(status, live, expected):
    assert gr.action_for(status, live=live) == expected


async def test_confirmed_grant_is_stamped_and_nothing_else_is_written():
    outcomes = await gr.check_all([_grant()], _client("Application deadline: 31 December 2026."), live=True, today=TODAY)
    assert outcomes[0].status == ver.CONFIRMED and outcomes[0].action == gr.STAMPED
    sb = _supabase()
    assert gr.apply_stamps(sb, outcomes, TODAY) == 1
    sb.table.assert_called_with("grant_database")
    sb.table.return_value.update.assert_called_once_with({"last_verified": "2026-10-08"})
    sb.table.return_value.update.return_value.eq.assert_called_once_with("id", "g1")


@pytest.mark.parametrize(
    "page",
    [
        "Closing date: 30 November 2026",                     # changed
        "Applications are now closed.",                       # closed
        "MDAG supports digital adoption.",                    # no signal
    ],
)
async def test_changed_closed_and_unclear_pages_never_write_to_the_database(page):
    outcomes = await gr.check_all([_grant()], _client(page), live=True, today=TODAY)
    sb = _supabase()
    assert gr.apply_stamps(sb, outcomes, TODAY) == 0
    sb.table.return_value.update.assert_not_called()


async def test_a_changed_deadline_is_reported_with_both_dates_and_the_source():
    out = (await gr.check_all([_grant()], _client("Closing date: 30 November 2026"), live=True, today=TODAY))[0]
    assert out.action == gr.NEEDS_REVIEW
    assert (out.db_deadline, out.found_deadline) == ("2026-12-31", "2026-11-30")
    assert out.source_url == "https://mdec.my/mdag"


async def test_dry_run_plans_but_writes_nothing():
    outcomes = await gr.check_all([_grant()], _client("Deadline: 31 December 2026"), live=False, today=TODAY)
    assert outcomes[0].action == gr.WOULD_STAMP
    sb = _supabase()
    assert gr.apply_stamps(sb, outcomes, TODAY) == 0
    sb.table.assert_not_called()


async def test_result_from_another_domain_is_never_trusted_or_stamped():
    outcomes = await gr.check_all(
        [_grant()], _client("Deadline: 31 December 2026", url="https://evil.example/x"), live=True, today=TODAY
    )
    assert outcomes[0].status == ver.UNAVAILABLE and outcomes[0].action == gr.NONE


async def test_one_failing_stamp_does_not_stop_the_rest():
    outcomes = await gr.check_all(
        [_grant(1), _grant(2)], _client("Deadline: 31 December 2026"), live=True, today=TODAY
    )
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = [RuntimeError("boom"), MagicMock()]
    assert gr.apply_stamps(sb, outcomes, TODAY) == 1
    assert sorted(o.action for o in outcomes) == [gr.NONE, gr.STAMPED]


async def test_the_nightly_job_does_not_use_the_redis_cache():
    with patch.object(ver, "get_cached_result", new=AsyncMock(return_value={"status": "confirmed"})) as get, \
         patch.object(ver, "set_cached_result", new=AsyncMock()) as put:
        client = _client("Deadline: 31 December 2026")
        await gr.check_all([_grant()], client, live=True, today=TODAY)
    get.assert_not_called()
    put.assert_not_called()
    client.search.assert_awaited()  # a fresh search, not a stale cached answer


# ── reporting ────────────────────────────────────────────────────────────────

async def test_summary_lists_what_needs_a_human_and_says_when_nothing_was_written():
    grants = [_grant(1), _grant(2, programme_name="Moved Grant")]
    client = MagicMock()
    pages = {"Grant 1": "Deadline: 31 December 2026", "Moved Grant": "Closing date: 30 November 2026"}
    client.search = AsyncMock(side_effect=lambda q, **k: {"results": [{"url": "https://mdec.my/x", "content": next(v for n, v in pages.items() if n in q)}]})
    outcomes = await gr.check_all(grants, client, live=False, today=TODAY)
    text = gr.render_summary(outcomes, live=False, today=TODAY)
    assert "dry-run: nothing was written" in text
    assert "Needs a human (the database was NOT changed)" in text
    assert "Moved Grant" in text and "2026-11-30" in text
    assert "Would stamp" in text


def test_workflow_command_syntax_in_names_is_neutralised():
    assert "::" not in gr._clean("Evil::error::pwned\nline2")
    assert "\n" not in gr._clean("a\nb")


def test_all_checks_failing_in_search_is_detected_but_a_mixed_run_is_not():
    failed = gr.Outcome("1", "A", "X", ver.UNAVAILABLE, "search_failed", None, None, None, gr.NONE)
    fine = gr.Outcome("2", "B", "X", ver.CONFIRMED, None, None, None, None, gr.STAMPED)
    assert gr.all_checks_failed([failed, failed]) is True
    assert gr.all_checks_failed([failed, fine]) is False
    assert gr.all_checks_failed([]) is False


# ── main(): exit codes and guards ────────────────────────────────────────────

def test_main_without_a_tavily_key_skips_cleanly(capsys):
    with patch.object(gr.settings, "tavily_api_key", ""):
        assert gr.main([]) == 0
    assert "TAVILY_API_KEY is not set" in capsys.readouterr().out


def test_main_refuses_to_run_against_the_dev_placeholder_database(capsys):
    with patch.object(gr.settings, "tavily_api_key", "tvly-test"), \
         patch.object(gr.settings, "supabase_url", "http://localhost:54321"):
        assert gr.main([]) == 1
    assert "not configured" in capsys.readouterr().out


def _configured():
    return patch.multiple(
        gr.settings, tavily_api_key="tvly-test", supabase_url="https://x.supabase.co", supabase_service_key="real-key"
    )


def test_main_fails_loudly_when_every_check_fails_in_search(capsys, tmp_path):
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[_grant(1), _grant(2)])
    with _configured(), patch("supabase.create_client", return_value=sb), \
         patch.object(ver, "make_client", return_value=_client(RuntimeError("401 invalid api key"))):
        assert gr.main(["--report-json", str(tmp_path / "r.json")]) == 1
    assert "every check failed" in capsys.readouterr().out


def test_main_dry_run_writes_report_and_no_database_changes(capsys, tmp_path):
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[_grant(1)])
    report = tmp_path / "r.json"
    with _configured(), patch("supabase.create_client", return_value=sb), \
         patch.object(ver, "make_client", return_value=_client("Closing date: 30 November 2026")):
        code = gr.main(["--report-json", str(report)])
    out = capsys.readouterr().out
    assert code == 0  # a changed deadline is a warning, not a failed job
    assert "::warning title=Grant changed::" in out
    sb.table.return_value.update.assert_not_called()
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data[0]["status"] == "changed" and data[0]["found_deadline"] == "2026-11-30"


def test_main_live_stamps_only_confirmed_grants(capsys):
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_grant(1), _grant(2, application_deadline="2027-03-31")]
    )
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    with _configured(), patch("supabase.create_client", return_value=sb), \
         patch.object(ver, "make_client", return_value=_client("Application deadline: 31 December 2026")):
        assert gr.main(["--live"]) == 0
    # grant 1 matches the page (stamped); grant 2's recorded deadline differs (reported only)
    sb.table.return_value.update.assert_called_once()
    assert sb.table.return_value.update.call_args.args[0].keys() == {"last_verified"}
    assert "stamped=1 checked=2" in capsys.readouterr().out
