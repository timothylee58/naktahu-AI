"""
Version-controlled registry of ingestion sources for document_chunks — the
table rag_node's hybrid_search actually queries (Trap #14: scripts/ingest.py
feeds dosm_documents, which live RAG does NOT read).

Before this module, ingestion sources existed only as --feed-url arguments in
someone's shell history: nothing in the repo recorded which URLs had been
ingested, with which domain/ministry attribution, or whether a source was an
RSS feed or a plain HTML page. This registry is that record.

It is a typed Python module rather than a JSON/YAML data file so it gets the
same pyflakes + type coverage as the rest of the codebase, and so
scripts/ingest_feed.py can validate entries against its own _VALID_DOMAINS at
import time in tests.

Usage:
    python -m scripts.ingest_feed --source invest-malaysia-gov --dry-run

Adding a source: append a Source(...) below. Domain MUST be one of the
canonical domains in migration 016 as widened by migration 026 and renamed
by migration 027 (Trap #6: government, education, legal, finance,
healthcare, epf, tax, business, immigration, culture, parliament) — never
invent a new one here.
URLs must be real, verified pages; never guess a feed URL.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["rss", "html"]
SourceLanguage = Literal["bm", "en", "zh"]


@dataclass(frozen=True)
class Source:
    """One ingestion source. `name` is the CLI selector (--source <name>)."""

    name: str
    url: str
    kind: SourceKind
    domain: str
    ministry: str
    language: SourceLanguage
    notes: str


SOURCES: tuple[Source, ...] = (
    Source(
        name="invest-malaysia-gov",
        url="https://www.investmalaysia.gov.my",
        kind="html",
        domain="business",
        ministry="Malaysian Investment Development Authority (MIDA)",
        language="en",
        notes=(
            "National investment-promotion portal (MIDA). HTML landing page, not a "
            "feed — ingested via --kind html. Feeds the business/grant/investor "
            "answer surfaces."
        ),
    ),
    Source(
        name="invest-malaysia-mida-eip",
        url="https://investmalaysia.mida.gov.my/EIP/InvestMalaysia.aspx",
        kind="html",
        domain="business",
        ministry="Malaysian Investment Development Authority (MIDA)",
        language="en",
        notes=(
            "MIDA Electronic Investment Portal (EIP) entry page — ASP.NET WebForms "
            "HTML, no feed available. Ingested via --kind html."
        ),
    ),
)

SOURCES_BY_NAME: dict[str, Source] = {s.name: s for s in SOURCES}


def get_source(name: str) -> Source:
    """Look up a registered source by name, or raise with the valid choices."""
    try:
        return SOURCES_BY_NAME[name]
    except KeyError:
        raise KeyError(
            f"unknown source {name!r} — registered sources: "
            f"{', '.join(sorted(SOURCES_BY_NAME))}"
        ) from None
