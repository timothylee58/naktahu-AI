from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import main as api_main
from app.agents.router_node import _VALID_DOMAINS
from middleware.rate_limit import anonymous_limiter, authenticated_limiter

# Obviously-fake fixture data — never real MP/bill/constituency records.
_FAKE_MP = {
    "mp_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    "full_name": "Test MP",
    "party": "Test Party",
    "constituency_name": "Testville",
    "attendance_rate": 0.9,
    "questions_count": 3,
    "bills_sponsored": 1,
    "recent_votes": [],
}


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)

    def fake_from_url(*args, **kwargs):
        return redis_client

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    table_mock = MagicMock()
    table_mock.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.select.return_value.limit.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    # get_mp_by_constituency's office_* follow-up lookup (migration 049):
    # .table("mp_profiles").select(...).eq("id", mp_id).limit(1).execute()
    table_mock.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = MagicMock(data=None)

    sb = MagicMock()
    sb.table.return_value = table_mock
    sb.rpc.return_value = rpc_mock

    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, sb, table_mock, rpc_mock


def test_get_mp_by_constituency_happy_path(client):
    c, sb, table_mock, rpc_mock = client
    rpc_mock.execute.return_value = MagicMock(data=[_FAKE_MP])

    res = c.get("/api/v1/parliament/mp/P999")
    assert res.status_code == 200, res.text
    assert res.json()["full_name"] == "Test MP"
    sb.rpc.assert_called_with("get_mp_by_constituency", {"p_code": "P999"})


def test_get_mp_by_constituency_includes_office_contact_when_present(client):
    """office_address/phone/email (migration 049) are fetched by mp_id and
    merged into the constituency-lookup response — not selected by the
    get_mp_by_constituency() SQL function itself (that function predates
    the columns), so this is a real follow-up query, not a passthrough."""
    c, sb, table_mock, rpc_mock = client
    rpc_mock.execute.return_value = MagicMock(data=[_FAKE_MP])
    table_mock.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"office_address": "Dewan Rakyat, Parlimen Malaysia", "office_phone": None, "office_email": None}]
    )

    res = c.get("/api/v1/parliament/mp/P999")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["office_address"] == "Dewan Rakyat, Parlimen Malaysia"
    assert body["office_phone"] is None


def test_get_mp_by_constituency_office_contact_absent_stays_absent(client):
    """No fabricated fallback when nothing has been ingested into the new
    columns yet — the response simply carries no office_* keys, never a
    placeholder string."""
    c, sb, table_mock, rpc_mock = client
    rpc_mock.execute.return_value = MagicMock(data=[_FAKE_MP])
    # Default fixture mock already returns data=[] for the office lookup.

    res = c.get("/api/v1/parliament/mp/P999")
    assert res.status_code == 200, res.text
    assert "office_address" not in res.json()


def test_get_mp_by_constituency_not_found(client):
    c, sb, table_mock, rpc_mock = client
    rpc_mock.execute.return_value = MagicMock(data=[])

    res = c.get("/api/v1/parliament/mp/P999")
    assert res.status_code == 404


def test_get_mp_by_constituency_malformed_code_404(client):
    c, *_ = client
    res = c.get("/api/v1/parliament/mp/not valid!!")
    assert res.status_code == 404


def test_search_mp_happy_path(client):
    c, sb, table_mock, rpc_mock = client
    table_mock.select.return_value.or_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "x", "full_name": "Test MP", "constituency_code": "P999"}]
    )

    res = c.get("/api/v1/parliament/mp/search", params={"q": "Test"})
    assert res.status_code == 200, res.text
    assert res.json()["results"][0]["full_name"] == "Test MP"


def test_search_mp_empty_results(client):
    c, *_ = client
    res = c.get("/api/v1/parliament/mp/search", params={"q": "Nobody"})
    assert res.status_code == 200
    assert res.json()["results"] == []


def test_search_mp_rejects_short_query(client):
    c, *_ = client
    res = c.get("/api/v1/parliament/mp/search", params={"q": "a"})
    assert res.status_code == 422


def test_bill_votes_happy_path(client):
    c, sb, table_mock, rpc_mock = client
    rpc_mock.execute.return_value = MagicMock(
        data=[{"vote": "for", "vote_count": 2, "party_breakdown": {"Test Party": 2}}]
    )

    res = c.get("/api/v1/parliament/bills/D.R. 99-2026/votes")
    assert res.status_code == 200, res.text
    assert res.json()["summary"][0]["vote"] == "for"


def test_bill_votes_not_found(client):
    c, sb, table_mock, rpc_mock = client
    rpc_mock.execute.return_value = MagicMock(data=[])

    res = c.get("/api/v1/parliament/bills/D.R. 99-2026/votes")
    assert res.status_code == 404


def test_constituencies_happy_path(client):
    c, sb, table_mock, rpc_mock = client
    table_mock.select.return_value.limit.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"code": "P999", "name": "Testville", "state": "Test State"}]
    )

    res = c.get("/api/v1/parliament/constituencies", params={"state": "Test State"})
    assert res.status_code == 200, res.text
    assert res.json()["results"][0]["code"] == "P999"


def test_constituencies_no_filter(client):
    c, sb, table_mock, rpc_mock = client
    table_mock.select.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"code": "P999", "name": "Testville"}]
    )

    res = c.get("/api/v1/parliament/constituencies")
    assert res.status_code == 200, res.text


def test_constituencies_rejects_bad_limit(client):
    c, *_ = client
    res = c.get("/api/v1/parliament/constituencies", params={"limit": 0})
    assert res.status_code == 422


def test_all_endpoints_503_when_supabase_unavailable(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)

    assert c.get("/api/v1/parliament/mp/P999").status_code == 503
    assert c.get("/api/v1/parliament/mp/search", params={"q": "Test"}).status_code == 503
    assert c.get("/api/v1/parliament/bills/D.R. 99-2026/votes").status_code == 503
    assert c.get("/api/v1/parliament/constituencies").status_code == 503


def test_no_auth_required_for_mp_lookup(client):
    c, sb, table_mock, rpc_mock = client
    rpc_mock.execute.return_value = MagicMock(data=[_FAKE_MP])

    res = c.get("/api/v1/parliament/mp/P999")  # no Authorization header
    assert res.status_code == 200, res.text


def test_parliament_domain_in_canonical_domain_list():
    """Migration 026 resolved the Trap #6 deferral recorded in
    025_parliament_watch.sql by widening the canonical domain list; migration
    027 then renamed that domain slug from 'hansard' to 'parliament' so it
    matches every other artefact in this vertical (parliament_bills,
    parliament_sessions, routers/parliament.py, scripts/ingest_parliament/) —
    'hansard' was the one leftover mismatched name. See
    027_rename_hansard_domain_to_parliament.sql for the CHECK-constraint
    rename and scripts/ingest_feed.py for its copy of the same list.
    """
    assert "parliament" in _VALID_DOMAINS
    assert "hansard" not in _VALID_DOMAINS


# ── GET /api/v1/parliament/postcode/{postcode} (migration 054) ──────────────

_FAKE_POSTCODE_MP = {
    "full_name": "Test MP",
    "salutation": "YB",
    "constituency_code": "P999",
    "constituency_name": "Testville",
    "state": "Test State",
    "party": "Test Party",
    "coalition": None,
    "parlimen_url": None,
    "office_address": None,
    "office_phone": None,
    "office_email": None,
}


def _route_tables(sb, crosswalk: list[dict], mps: list[dict]) -> tuple[MagicMock, MagicMock]:
    crosswalk_table, mp_table = MagicMock(), MagicMock()
    crosswalk_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=crosswalk)
    mp_table.select.return_value.in_.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=mps)
    sb.table.side_effect = lambda name: crosswalk_table if name == "postcode_constituencies" else mp_table
    return crosswalk_table, mp_table


def test_postcode_lookup_returns_every_mp_for_a_straddling_postcode(client):
    c, sb, _, _ = client
    second = {**_FAKE_POSTCODE_MP, "full_name": "Other MP", "constituency_code": "P998"}
    _, mp_table = _route_tables(
        sb,
        [{"constituency_code": "P999"}, {"constituency_code": "P998"}],
        [_FAKE_POSTCODE_MP, second],
    )

    res = c.get("/api/v1/parliament/postcode/50450")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["postcode"] == "50450"
    assert [m["constituency_code"] for m in body["mps"]] == ["P998", "P999"]
    codes = mp_table.select.return_value.in_.call_args.args[1]
    assert codes == ["P998", "P999"]


def test_postcode_lookup_empty_when_crosswalk_has_no_rows(client):
    c, sb, _, _ = client
    _, mp_table = _route_tables(sb, [], [])

    res = c.get("/api/v1/parliament/postcode/50450")
    assert res.status_code == 200
    assert res.json() == {"postcode": "50450", "mps": []}
    mp_table.select.assert_not_called()


def test_postcode_lookup_degrades_when_table_missing(client):
    """Before migration 054 is applied the crosswalk query errors: return no
    MPs (the landing page keeps its state-only line), not a 500."""
    c, sb, _, _ = client
    crosswalk_table, _ = _route_tables(sb, [], [])
    crosswalk_table.select.return_value.eq.return_value.execute.side_effect = Exception(
        'relation "postcode_constituencies" does not exist'
    )

    res = c.get("/api/v1/parliament/postcode/50450")
    assert res.status_code == 200
    assert res.json()["mps"] == []


@pytest.mark.parametrize("bad", ["5045", "504500", "5045a", "abcde"])
def test_postcode_lookup_rejects_malformed_postcode(client, bad):
    c, _, _, _ = client
    assert c.get(f"/api/v1/parliament/postcode/{bad}").status_code == 404


def test_postcode_lookup_503_when_supabase_unavailable(client):
    c, _, _, _ = client
    original = api_main.app.state.supabase
    api_main.app.state.supabase = None
    try:
        assert c.get("/api/v1/parliament/postcode/50450").status_code == 503
    finally:
        api_main.app.state.supabase = original


def test_postcode_lookup_rate_limited(client):
    c, sb, _, _ = client
    _route_tables(sb, [], [])
    statuses = [c.get("/api/v1/parliament/postcode/50450").status_code for _ in range(61)]
    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429
