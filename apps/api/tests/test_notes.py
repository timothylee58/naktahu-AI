"""Personal notes: owner-scoped CRUD, search, caps, validation, 503 degradation."""
import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter
from routers.notes import MAX_NOTES_PER_USER

NOTE_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
ROW = {
    "id": NOTE_ID, "user_id": "user-a", "title": "Spouse relief", "body": "RM4,000 for a spouse",
    "tags": ["tax"], "source": None, "created_at": "2026-11-28T00:00:00+00:00",
    "updated_at": "2026-11-28T00:00:00+00:00",
}


def _auth(sub: str = "user-a") -> dict[str, str]:
    tok = jwt.encode(
        {"sub": sub, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)

    table = MagicMock()
    # any select(...).limit(1) health probe; count query ends in .limit(1).execute
    table.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    q = table.select.return_value.eq.return_value
    q.limit.return_value.execute.return_value = MagicMock(data=[], count=0)
    table.insert.return_value.execute.return_value = MagicMock(data=[ROW])
    sb = MagicMock()
    sb.table.return_value = table
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)
    anonymous_limiter.reset()
    authenticated_limiter.reset()
    with TestClient(api_main.app) as c:
        yield c, table


def test_anonymous_is_401(client):
    c, _ = client
    assert c.get("/api/v1/notes").status_code == 401
    assert c.post("/api/v1/notes", json={"title": "x"}).status_code == 401
    assert c.delete(f"/api/v1/notes/{NOTE_ID}").status_code == 401


def test_create_scopes_to_caller_and_ignores_body_user_id(client):
    c, table = client
    r = c.post(
        "/api/v1/notes", headers=_auth("user-a"),
        json={"title": "Spouse relief", "body": "RM4,000", "tags": [" Tax ", "tax", "EPF"],
              "user_id": "someone-else"},
    )
    assert r.status_code == 201
    row = table.insert.call_args.args[0]
    assert row["user_id"] == "user-a"
    assert row["tags"] == ["tax", "epf"]  # trimmed, lower-cased, de-duplicated


def test_create_keeps_answer_source(client):
    c, table = client
    src = {"query": "spouse relief?", "citations": [
        {"title": "Jadual", "ministry": "LHDN", "url": "https://www.hasil.gov.my", "effective_date": "2026-01-01"}]}
    c.post("/api/v1/notes", headers=_auth(), json={"title": "t", "source": src})
    assert table.insert.call_args.args[0]["source"]["citations"][0]["ministry"] == "LHDN"


def test_create_blocked_at_cap(client):
    c, table = client
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[], count=MAX_NOTES_PER_USER)
    r = c.post("/api/v1/notes", headers=_auth(), json={"title": "one too many"})
    assert r.status_code == 409
    table.insert.assert_not_called()


@pytest.mark.parametrize("bad", [
    {"title": ""},
    {"title": "x" * 201},
    {"title": "ok", "body": "x" * 20001},
    {"title": "ok", "tags": ["a"] * 11},
    {"title": "ok", "tags": ["x" * 41]},
    {"title": "ok", "tags": [" "]},
    {"title": "ok", "source": {"citations": [{"url": "javascript:alert(1)"}]}},
    {"title": "ok", "source": {"citations": [{"effective_date": "yesterday"}]}},
    {"title": "ok", "source": {"citations": [{}] * 11}},
])
def test_create_validation_rejects(client, bad):
    c, _ = client
    assert c.post("/api/v1/notes", headers=_auth(), json=bad).status_code == 422


def test_list_is_owner_scoped_and_returns_snippets_not_bodies(client):
    c, table = client
    long = {**ROW, "body": "word " * 100, "source": {"query": "q"}}
    chain = table.select.return_value.eq.return_value
    chain.order.return_value.range.return_value.execute.return_value = MagicMock(data=[long])
    r = c.get("/api/v1/notes", headers=_auth("user-a"))
    assert r.status_code == 200
    n = r.json()["notes"][0]
    assert len(n["snippet"]) <= 160 and "body" not in n and n["from_answer"] is True
    table.select.return_value.eq.assert_called_with("user_id", "user-a")


def test_search_and_tag_filters_are_applied(client):
    c, table = client
    chain = table.select.return_value.eq.return_value
    chain.text_search.return_value.contains.return_value.order.return_value.range.return_value.execute.return_value = MagicMock(data=[ROW])
    r = c.get("/api/v1/notes?q=spouse&tag=Tax", headers=_auth())
    assert r.status_code == 200 and len(r.json()["notes"]) == 1
    chain.text_search.assert_called_once()
    assert chain.text_search.call_args.args[:2] == ("search_tsv", "spouse")
    chain.text_search.return_value.contains.assert_called_with("tags", ["tax"])


@pytest.mark.parametrize("qs", ["limit=0", "limit=101", "offset=-1", "q=" + "x" * 201])
def test_list_param_bounds(client, qs):
    c, _ = client
    assert c.get(f"/api/v1/notes?{qs}", headers=_auth()).status_code == 422


def test_get_other_users_or_missing_note_is_404(client):
    c, table = client
    table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    assert c.get(f"/api/v1/notes/{NOTE_ID}", headers=_auth("user-b")).status_code == 404
    assert c.get("/api/v1/notes/not-a-uuid", headers=_auth()).status_code == 404


def test_get_returns_full_note(client):
    c, table = client
    table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[ROW])
    r = c.get(f"/api/v1/notes/{NOTE_ID}", headers=_auth())
    assert r.status_code == 200 and r.json()["body"] == "RM4,000 for a spouse"


def test_patch_updates_only_sent_fields_scoped_to_owner(client):
    c, table = client
    upd = table.update.return_value.eq.return_value.eq.return_value
    upd.execute.return_value = MagicMock(data=[{**ROW, "title": "New"}])
    r = c.patch(f"/api/v1/notes/{NOTE_ID}", headers=_auth("user-a"), json={"title": "New"})
    assert r.status_code == 200
    changes = table.update.call_args.args[0]
    assert changes["title"] == "New" and "body" not in changes and "updated_at" in changes
    table.update.return_value.eq.assert_called_with("user_id", "user-a")


@pytest.mark.parametrize("bad", [{}, {"title": None}, {"body": None}, {"title": ""}])
def test_patch_rejects_empty_or_null(client, bad):
    c, _ = client
    assert c.patch(f"/api/v1/notes/{NOTE_ID}", headers=_auth(), json=bad).status_code == 422


def test_patch_missing_note_is_404(client):
    c, table = client
    table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    assert c.patch(f"/api/v1/notes/{NOTE_ID}", headers=_auth(), json={"body": "x"}).status_code == 404


def test_delete_owner_scoped_and_404_when_not_found(client):
    c, table = client
    dele = table.delete.return_value.eq.return_value.eq.return_value
    dele.execute.return_value = MagicMock(data=[ROW])
    assert c.delete(f"/api/v1/notes/{NOTE_ID}", headers=_auth("user-a")).status_code == 204
    table.delete.return_value.eq.assert_called_with("user_id", "user-a")
    dele.execute.return_value = MagicMock(data=[])
    assert c.delete(f"/api/v1/notes/{NOTE_ID}", headers=_auth("user-b")).status_code == 404


def test_503_without_supabase_and_until_migration_applied(client):
    c, table = client
    table.select.return_value.eq.return_value.order.return_value.range.return_value.execute.side_effect = RuntimeError("relation does not exist")
    assert c.get("/api/v1/notes", headers=_auth()).status_code == 503
    api_main.app.state.supabase = None
    assert c.get("/api/v1/notes", headers=_auth()).status_code == 503
    assert c.post("/api/v1/notes", headers=_auth(), json={"title": "x"}).status_code == 503


# ── step 5: links, export, stale ─────────────────────────────────────────────
import io
import zipfile
from datetime import date, timedelta

from routers.notes import _compute_links, _reasons_for, _safe_filename, _to_markdown, _wikilinks

A = {"id": "a", "title": "Spouse relief", "body": "See [[EPF basics]] and [[Missing note]] and [[epf basics|alias]]"}
B = {"id": "b", "title": "EPF basics", "body": "Related: [[Spouse relief]]"}
C = {"id": "c", "title": "Other", "body": "nothing here"}


def test_wikilinks_parse_dedupe_case_insensitively():
    assert _wikilinks(A["body"]) == ["EPF basics", "Missing note"]
    assert _wikilinks("[[ ]] [[a\nb]] [[x]]") == ["x"]


def test_links_resolve_outgoing_and_backlinks():
    links = _compute_links(A, [A, B, C])
    assert [(n.title, n.id) for n in links.outgoing] == [("EPF basics", "b"), ("Missing note", None)]
    assert [n.id for n in links.backlinks] == ["b"]
    assert _compute_links(C, [A, B, C]).backlinks == []


def test_export_filenames_cannot_escape_the_zip():
    used: set[str] = set()
    names = [_safe_filename(t, used) for t in ["../../etc/passwd", "a/b\\c", "", "Same", "same"]]
    assert all("/" not in n and "\\" not in n and ".." not in n for n in names)
    assert len({n.lower() for n in names}) == len(names)  # duplicates get distinct names


def test_markdown_has_front_matter_and_keeps_wikilinks():
    md = _to_markdown({
        "title": 'Quote "me": colon', "tags": ["tax"], "created_at": "c", "updated_at": "u",
        "body": "Link [[B]]",
        "source": {"query": "q?", "citations": [{"title": "T", "ministry": "LHDN", "url": "https://x.gov.my"}]},
    })
    assert md.startswith("---\ntitle: \"Quote \\\"me\\\": colon\"\n")
    assert 'tags: ["tax"]' in md and "Link [[B]]" in md and "https://x.gov.my" in md


def test_export_endpoint_returns_a_zip_of_only_the_callers_notes(client):
    c, table = client
    table.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=[{**ROW, "title": "One"}, {**ROW, "id": "x2", "title": "Two"}])
    r = c.get("/api/v1/notes/export", headers=_auth("user-a"))
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert sorted(z.namelist()) == ["One.md", "Two.md"]
    table.select.return_value.eq.assert_called_with("user_id", "user-a")


def test_export_route_is_not_swallowed_by_note_id(client):
    c, table = client
    table.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
    assert c.get("/api/v1/notes/export", headers=_auth()).status_code == 200


def test_links_endpoint_404_for_other_users_note(client):
    c, table = client
    table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[A, B])
    assert c.get(f"/api/v1/notes/{NOTE_ID}/links", headers=_auth("user-b")).status_code == 404
    assert c.get("/api/v1/notes/nope/links", headers=_auth()).status_code == 404


TODAY = date(2026, 11, 28)
URL = "https://www.hasil.gov.my/x"


def test_stale_superseded_expired_newer_and_fresh():
    cite = [{"url": URL, "effective_date": "2025-01-01"}]
    assert _reasons_for(cite, {URL: [{"superseded_by": "z"}]}, TODAY) == ["superseded"]
    assert _reasons_for(cite, {URL: [{"effective_until": "2026-01-01"}]}, TODAY) == ["expired"]
    assert _reasons_for(cite, {URL: [{"effective_date": "2025-01-01"}, {"effective_date": "2026-01-01"}]}, TODAY) == ["newer_version"]
    assert _reasons_for(cite, {URL: [{"effective_date": "2025-01-01"}]}, TODAY) == []


def test_stale_is_silent_when_unsure():
    # no chunks for the URL, no cited date, or one live chunk among superseded ones
    assert _reasons_for([{"url": URL}], {}, TODAY) == []
    assert _reasons_for([{"url": URL}], {URL: [{"effective_date": "2026-01-01"}]}, TODAY) == []
    assert _reasons_for([{"url": URL}], {URL: [{"superseded_by": "z"}, {}]}, TODAY) == []
    future = (TODAY + timedelta(days=5)).isoformat()
    assert _reasons_for([{"url": URL}], {URL: [{"effective_until": future}]}, TODAY) == []


def test_stale_endpoint_flags_only_affected_notes(client):
    c, table = client
    notes = [
        {"id": "n1", "title": "Old rule", "source": {"citations": [{"url": URL, "effective_date": "2024-01-01"}]}},
        {"id": "n2", "title": "Fine", "source": {"citations": [{"url": "https://ok.gov.my"}]}},
    ]
    table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=notes + [{"id": "n3", "title": "Manual", "source": None}])
    table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[
        {"source_url": URL, "effective_date": "2025-06-01", "effective_until": None, "superseded_by": None}])
    r = c.get("/api/v1/notes/stale", headers=_auth())
    assert r.status_code == 200
    assert r.json()["stale"] == [{"id": "n1", "title": "Old rule", "reasons": ["newer_version"]}]
