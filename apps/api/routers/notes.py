"""routers/notes.py — a signed-in user's personal notes.

POST   /api/v1/notes        create a note (optionally saved from an answer)
GET    /api/v1/notes        list, newest first; ?q= keyword search, ?tag= filter
GET    /api/v1/notes/{id}   one full note
PATCH  /api/v1/notes/{id}   edit title / body / tags
DELETE /api/v1/notes/{id}   delete

Open to every signed-in user (Free and Pro), with a per-user cap so it cannot be
used as free bulk storage. Notes are the user's own words: they are never added
to the public corpus and never used to answer anyone else.

Service-role client => every query filters on the caller's user_id. Mounted in
main.py (the single app). Needs migration 064; 503 until it is applied.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import date, datetime, timezone
from typing import Annotated, Any, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import Response as RawResponse
from pydantic import BaseModel, Field, field_validator

from app.agents.runtime import execute_query
from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])

MAX_NOTES_PER_USER = 200
_UNAVAILABLE = "Notes are temporarily unavailable"
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_SNIPPET_CHARS = 160


def _clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for tag in tags:
        t = " ".join(tag.split()).lower()
        if not (1 <= len(t) <= 40):
            raise ValueError("each tag must be 1-40 characters")
        if t not in out:
            out.append(t)
    return out


class SourceCitation(BaseModel):
    title: str = Field("", max_length=300)
    ministry: str = Field("", max_length=200)
    url: Optional[str] = Field(None, max_length=2000, pattern=r"^https?://")
    effective_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class NoteSource(BaseModel):
    """Where a saved answer came from. Kept so a note can show its provenance."""

    query: str = Field("", max_length=2000)
    citations: list[SourceCitation] = Field(default_factory=list, max_length=10)


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field("", max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=10)
    source: Optional[NoteSource] = None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return _clean_tags(v)


class NotePatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    body: Optional[str] = Field(None, max_length=20000)
    tags: Optional[list[str]] = Field(None, max_length=10)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return None if v is None else _clean_tags(v)


class NoteSummary(BaseModel):
    id: str
    title: str
    tags: list[str]
    snippet: str
    from_answer: bool
    updated_at: str


class Note(BaseModel):
    id: str
    title: str
    body: str
    tags: list[str]
    source: Optional[dict[str, Any]] = None
    created_at: str
    updated_at: str


class NoteList(BaseModel):
    notes: list[NoteSummary]


def _supabase_or_503(request: Request) -> Any:
    sb = getattr(request.app.state, "supabase", None)
    if not sb:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return sb


def _check_id(note_id: str) -> str:
    if not _UUID_RE.match(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return note_id


def _to_note(row: dict[str, Any]) -> Note:
    return Note(
        id=str(row["id"]),
        title=row.get("title") or "",
        body=row.get("body") or "",
        tags=list(row.get("tags") or []),
        source=row.get("source"),
        created_at=str(row.get("created_at") or ""),
        updated_at=str(row.get("updated_at") or ""),
    )


def _to_summary(row: dict[str, Any]) -> NoteSummary:
    body = " ".join((row.get("body") or "").split())
    return NoteSummary(
        id=str(row["id"]),
        title=row.get("title") or "",
        tags=list(row.get("tags") or []),
        snippet=body[:_SNIPPET_CHARS],
        from_answer=bool(row.get("source")),
        updated_at=str(row.get("updated_at") or ""),
    )


async def _run(builder: Any, what: str) -> Any:
    try:
        return await execute_query(builder)
    except Exception as exc:  # noqa: BLE001 — table missing until migration 064 is applied
        log.warning("notes_query_failed", op=what, error=str(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)


@router.post("", response_model=Note, status_code=201)
@apply_query_rate_limit()
async def create_note(
    request: Request,
    response: Response,
    body: NoteCreate,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> Note:
    sb = _supabase_or_503(request)
    counted = await _run(
        sb.table("user_notes").select("id", count="exact").eq("user_id", user.user_id).limit(1),
        "count",
    )
    if (getattr(counted, "count", None) or 0) >= MAX_NOTES_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"You have reached the limit of {MAX_NOTES_PER_USER} notes. Delete one to add another.",
        )
    row: dict[str, Any] = {
        "user_id": user.user_id,
        "title": body.title,
        "body": body.body,
        "tags": body.tags,
        "source": body.source.model_dump() if body.source else None,
    }
    res = await _run(sb.table("user_notes").insert(row), "insert")
    rows = getattr(res, "data", None) or []
    if not rows:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    log.info("note_created", user_id=user.user_id)  # ids only, never note text
    return _to_note(rows[0])


@router.get("", response_model=NoteList)
@apply_query_rate_limit()
async def list_notes(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
    q: Annotated[Optional[str], Query(max_length=200)] = None,
    tag: Annotated[Optional[str], Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> NoteList:
    sb = _supabase_or_503(request)
    builder = (
        sb.table("user_notes")
        .select("id,title,body,tags,source,updated_at")
        .eq("user_id", user.user_id)
    )
    if q and q.strip():
        builder = builder.text_search(
            "search_tsv", q.strip(), options={"type": "websearch", "config": "simple"}
        )
    if tag and tag.strip():
        builder = builder.contains("tags", [" ".join(tag.split()).lower()])
    builder = builder.order("updated_at", desc=True).range(offset, offset + limit - 1)
    res = await _run(builder, "list")
    return NoteList(notes=[_to_summary(r) for r in (getattr(res, "data", None) or [])])


# ── Links, export and staleness ──────────────────────────────────────────────
# Registered BEFORE "/{note_id}": FastAPI matches in order, so a later
# "/export" would be captured as note_id="export" and 404.

_WIKILINK_RE = re.compile(r"\[\[([^\[\]\n|]{1,200})(?:\|[^\[\]\n]{0,200})?\]\]")
_MAX_URLS_CHECKED = 50


def _wikilinks(body: str) -> list[str]:
    seen: list[str] = []
    for m in _WIKILINK_RE.finditer(body or ""):
        title = " ".join(m.group(1).split())
        if title and title.lower() not in [x.lower() for x in seen]:
            seen.append(title)
    return seen


class LinkedNote(BaseModel):
    id: Optional[str] = None  # None = a [[link]] to a note that doesn't exist yet
    title: str


class NoteLinks(BaseModel):
    outgoing: list[LinkedNote]
    backlinks: list[LinkedNote]


def _compute_links(target: dict[str, Any], rows: list[dict[str, Any]]) -> NoteLinks:
    by_title = {(r.get("title") or "").strip().lower(): r for r in rows}
    outgoing = []
    for title in _wikilinks(target.get("body") or ""):
        hit = by_title.get(title.lower())
        outgoing.append(LinkedNote(id=str(hit["id"]) if hit else None, title=hit["title"] if hit else title))
    me = (target.get("title") or "").strip().lower()
    backlinks = [
        LinkedNote(id=str(r["id"]), title=r.get("title") or "")
        for r in rows
        if str(r["id"]) != str(target["id"])
        and me in [t.lower() for t in _wikilinks(r.get("body") or "")]
    ]
    return NoteLinks(outgoing=outgoing, backlinks=backlinks)


def _safe_filename(title: str, used: set[str]) -> str:
    # Letters, digits, space, dash, underscore only; no path separators or dots
    # can survive, so an exported name can never escape the zip's root.
    base = re.sub(r"[^\w\- ]+", "", title, flags=re.UNICODE).strip()[:80] or "note"
    name, n = base, 2
    while name.lower() in used:
        name = f"{base} {n}"
        n += 1
    used.add(name.lower())
    return f"{name}.md"


def _to_markdown(row: dict[str, Any]) -> str:
    """Obsidian-compatible: YAML front matter, then the body unchanged (so
    [[wikilinks]] keep working). json.dumps gives valid, safely quoted YAML strings."""
    fm = ["---", f"title: {json.dumps(row.get('title') or '', ensure_ascii=False)}"]
    tags = list(row.get("tags") or [])
    fm.append("tags: " + json.dumps(tags, ensure_ascii=False))
    fm.append(f"created: {json.dumps(str(row.get('created_at') or ''))}")
    fm.append(f"updated: {json.dumps(str(row.get('updated_at') or ''))}")
    src = row.get("source") or {}
    if src.get("query"):
        fm.append(f"source_query: {json.dumps(src['query'], ensure_ascii=False)}")
    cites = [c for c in (src.get("citations") or []) if c.get("url")]
    if cites:
        fm.append("sources:")
        for c in cites:
            label = " ".join(x for x in (c.get("ministry"), c.get("title")) if x)
            fm.append(f"  - {json.dumps(label + ' ' + c['url'], ensure_ascii=False)}")
    fm.append("---\n")
    return "\n".join(fm) + (row.get("body") or "") + "\n"


@router.get("/export")
@apply_query_rate_limit()
async def export_notes(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> RawResponse:
    """All of the caller's notes as a zip of markdown files (Obsidian-ready)."""
    sb = _supabase_or_503(request)
    res = await _run(
        sb.table("user_notes").select("*").eq("user_id", user.user_id).order("created_at"), "export"
    )
    rows = getattr(res, "data", None) or []
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            zf.writestr(_safe_filename(row.get("title") or "", used), _to_markdown(row))
    log.info("notes_exported", user_id=user.user_id, count=len(rows))
    return RawResponse(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="naktahu-notes.zip"'},
    )


StaleReason = Literal["superseded", "expired", "newer_version"]


class StaleNote(BaseModel):
    id: str
    title: str
    reasons: list[StaleReason]


class StaleNotes(BaseModel):
    stale: list[StaleNote]


def _parse_date(v: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _reasons_for(citations: list[dict[str, Any]], chunks_by_url: dict[str, list[dict[str, Any]]], today: date) -> list[str]:
    """Why the sources behind a saved answer may have moved on. Never says the
    note is wrong, only that its source has changed since it was saved."""
    reasons: list[str] = []
    for c in citations:
        chunks = chunks_by_url.get(c.get("url") or "")
        if not chunks:
            continue  # unknown source: say nothing rather than guess
        if all(ch.get("superseded_by") for ch in chunks):
            reasons.append("superseded")
            continue
        if all((u := _parse_date(ch.get("effective_until"))) is not None and u < today for ch in chunks):
            reasons.append("expired")
            continue
        cited = _parse_date(c.get("effective_date"))
        newest = max((d for d in (_parse_date(ch.get("effective_date")) for ch in chunks) if d), default=None)
        if cited and newest and newest > cited:
            reasons.append("newer_version")
    return [r for r in dict.fromkeys(reasons)]  # unique, order kept


@router.get("/stale", response_model=StaleNotes)
@apply_query_rate_limit()
async def stale_notes(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> StaleNotes:
    """Notes saved from an answer whose cited source has since been superseded,
    has expired, or has a newer version in our corpus."""
    sb = _supabase_or_503(request)
    res = await _run(
        sb.table("user_notes").select("id,title,source").eq("user_id", user.user_id),
        "stale-notes",
    )
    # Filtered here, not in PostgREST: the 200-note cap keeps this small.
    notes = [n for n in (getattr(res, "data", None) or []) if n.get("source")]
    urls: list[str] = []
    for n in notes:
        for c in (n.get("source") or {}).get("citations") or []:
            u = c.get("url")
            if u and u not in urls and len(urls) < _MAX_URLS_CHECKED:
                urls.append(u)
    chunks_by_url: dict[str, list[dict[str, Any]]] = {}
    if urls:
        cres = await _run(
            sb.table("document_chunks").select("source_url,effective_date,effective_until,superseded_by").in_("source_url", urls),
            "stale-chunks",
        )
        for ch in getattr(cres, "data", None) or []:
            chunks_by_url.setdefault(ch.get("source_url") or "", []).append(ch)
    today = datetime.now(timezone.utc).date()
    out: list[StaleNote] = []
    for n in notes:
        reasons = _reasons_for((n.get("source") or {}).get("citations") or [], chunks_by_url, today)
        if reasons:
            out.append(StaleNote(id=str(n["id"]), title=n.get("title") or "", reasons=reasons))  # type: ignore[arg-type]
    return StaleNotes(stale=out)


@router.get("/{note_id}/links", response_model=NoteLinks)
@apply_query_rate_limit()
async def note_links(
    request: Request,
    response: Response,
    note_id: str,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> NoteLinks:
    """[[Wikilinks]] out of this note, and the notes that link back to it."""
    sb = _supabase_or_503(request)
    res = await _run(sb.table("user_notes").select("id,title,body").eq("user_id", user.user_id), "links")
    rows = getattr(res, "data", None) or []
    wanted = _check_id(note_id).lower()
    target = next((r for r in rows if str(r["id"]).lower() == wanted), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return _compute_links(target, rows)


@router.get("/{note_id}", response_model=Note)
@apply_query_rate_limit()
async def get_note(
    request: Request,
    response: Response,
    note_id: str,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> Note:
    sb = _supabase_or_503(request)
    res = await _run(
        sb.table("user_notes").select("*").eq("user_id", user.user_id).eq("id", _check_id(note_id)).limit(1),
        "get",
    )
    rows = getattr(res, "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Note not found")
    return _to_note(rows[0])


@router.patch("/{note_id}", response_model=Note)
@apply_query_rate_limit()
async def patch_note(
    request: Request,
    response: Response,
    note_id: str,
    body: NotePatch,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> Note:
    sb = _supabase_or_503(request)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to update.")
    if any(v is None for v in changes.values()):
        raise HTTPException(status_code=422, detail="Fields cannot be null.")
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await _run(
        sb.table("user_notes").update(changes).eq("user_id", user.user_id).eq("id", _check_id(note_id)),
        "update",
    )
    rows = getattr(res, "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Note not found")
    return _to_note(rows[0])


@router.delete("/{note_id}", status_code=204, response_model=None)
@apply_query_rate_limit()
async def delete_note(
    request: Request,
    response: Response,
    note_id: str,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    sb = _supabase_or_503(request)
    res = await _run(
        sb.table("user_notes").delete().eq("user_id", user.user_id).eq("id", _check_id(note_id)),
        "delete",
    )
    if not (getattr(res, "data", None) or []):
        raise HTTPException(status_code=404, detail="Note not found")
