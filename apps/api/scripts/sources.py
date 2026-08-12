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
canonical domains in migration 016 as widened by migration 026, renamed
by migration 027, and further widened by migration 030 (Trap #6:
government, education, legal, finance, healthcare, epf, tax, business,
immigration, culture, parliament, property) — never invent a new one here.
URLs must be real, verified pages; never guess a feed URL.

The property/business/epf/legal entries below were found via WebSearch
(confirmed as real, indexed, official .gov.my / statutory-body domains —
not phishing lookalikes) but NOT content-verified via a direct fetch,
since this repo's sandbox blocks outbound HTTPS to gov.my domains at the
network egress proxy (not a site issue — a deliberate environment
restriction, see .github/workflows/ingest-sources.yml's header comment).
The scheduled ingestion workflow defaults every one of these to
--dry-run until a human confirms the parsed content looks right and
flips it to a real run — see that workflow for the exact mechanism.
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

    # ── property (migration 030) ────────────────────────────────────────────
    Source(
        name="jkptg-home",
        url="https://www.jkptg.gov.my/en/",
        kind="html",
        domain="property",
        ministry="Jabatan Ketua Pengarah Tanah dan Galian (JKPTG)",
        language="en",
        notes="Federal land administration department homepage.",
    ),
    Source(
        name="jkptg-e-tanah",
        url="https://www.jkptg.gov.my/en/penerbitan/e-tanah",
        kind="html",
        domain="property",
        ministry="Jabatan Ketua Pengarah Tanah dan Galian (JKPTG)",
        language="en",
        notes="JKPTG's own e-Tanah system explainer page (not the login portal).",
    ),
    Source(
        name="jkptg-strata-faq",
        url="https://www.jkptg.gov.my/en/soalan-lazim-3/104-faq/hakmilik-strata/pengurusan-skim-strata",
        kind="html",
        domain="property",
        ministry="Jabatan Ketua Pengarah Tanah dan Galian (JKPTG)",
        language="en",
        notes="JKPTG FAQ page on strata scheme management.",
    ),
    Source(
        name="dbkl-commissioner-of-buildings",
        url="https://www.dbkl.gov.my/en/pesuruhjaya-bangunan-cob/",
        kind="html",
        domain="property",
        ministry="Dewan Bandaraya Kuala Lumpur (DBKL)",
        language="en",
        notes="DBKL Commissioner of Buildings (COB) division overview — state-level strata enforcement example.",
    ),

    # ── business (SSM — registration/compliance beyond the MIDA investment pages) ──
    Source(
        name="ssm-home",
        url="https://www.ssm.com.my/",
        kind="html",
        domain="business",
        ministry="Suruhanjaya Syarikat Malaysia (SSM)",
        language="en",
        notes="Companies Commission of Malaysia homepage.",
    ),
    Source(
        name="ssm-annual-submission",
        url="https://www.ssm.com.my/Pages/Register_Business_Company_LLP/Company/Annual-Submission.aspx",
        kind="html",
        domain="business",
        ministry="Suruhanjaya Syarikat Malaysia (SSM)",
        language="en",
        notes="Official page on annual return / annual submission requirements for registered companies.",
    ),

    # ── epf (EIS/SOCSO employer registration + contribution facts — migration 030's domain split) ──
    Source(
        name="perkeso-home",
        url="https://www.perkeso.gov.my/en/",
        kind="html",
        domain="epf",
        ministry="Pertubuhan Keselamatan Sosial (PERKESO/SOCSO)",
        language="en",
        notes="PERKESO homepage.",
    ),
    Source(
        name="perkeso-employer-registration",
        url="https://www.perkeso.gov.my/en/our-services/employer-employee/employer-registration/184-our-services.html",
        kind="html",
        domain="epf",
        ministry="Pertubuhan Keselamatan Sosial (PERKESO/SOCSO)",
        language="en",
        notes="Employer registration requirements (30-day rule, Form 1/2, ASSIST Portal).",
    ),
    Source(
        name="perkeso-contribution-rates",
        url="https://www.perkeso.gov.my/en/rate-of-contribution.html",
        kind="html",
        domain="epf",
        ministry="Pertubuhan Keselamatan Sosial (PERKESO/SOCSO)",
        language="en",
        notes="SOCSO + EIS contribution rate schedules.",
    ),
    Source(
        name="perkeso-contributions-overview",
        url="https://www.perkeso.gov.my/en/our-services/employer-employee/contributions.html",
        kind="html",
        domain="epf",
        ministry="Pertubuhan Keselamatan Sosial (PERKESO/SOCSO)",
        language="en",
        notes="Contributions overview — EIS 0.2%/0.2% employer/employee split, wage ceiling.",
    ),

    # ── legal (termination rights, Employment Act, EIS *claims* — migration 030's domain split) ──
    Source(
        name="agc-employment-act-1955",
        url="https://lom.agc.gov.my/act-detail.php?type=amendment&act=A1651&lang=BI",
        kind="html",
        domain="legal",
        ministry="Attorney General's Chambers (AGC) — Laws of Malaysia",
        language="en",
        notes=(
            "AGC federal legislation portal's Employment Act 1955 detail page — the "
            "authoritative statute-text source. The full text itself is a linked PDF, "
            "not scrapeable via --kind html; this page's metadata/amendment history is."
        ),
    ),
    Source(
        name="jtksm-retrenchment-faq",
        url="https://jtksm.mohr.gov.my/en/frequently-asked-questions/employees-retrenchment",
        kind="html",
        domain="legal",
        ministry="Jabatan Tenaga Kerja Semenanjung Malaysia (JTKSM) / MOHR",
        language="en",
        notes="Official retrenchment FAQ — termination benefit calculation, VSS, notice obligations.",
    ),
    Source(
        name="jtksm-retrenchment-forms",
        url="https://jtksm.mohr.gov.my/en/services/employees-retrenchment/employees-retrenchment-forms",
        kind="html",
        domain="legal",
        ministry="Jabatan Tenaga Kerja Semenanjung Malaysia (JTKSM) / MOHR",
        language="en",
        notes="Retrenchment notification procedure (Borang PK) and requirements.",
    ),
    Source(
        name="perkeso-eis-benefits-application-guide",
        url="https://www.perkeso.gov.my/en/online/contributor/faedah-sip-new/eis-benefits-application-guide.html",
        kind="html",
        domain="legal",
        ministry="Pertubuhan Keselamatan Sosial (PERKESO/SOCSO) — EIS",
        language="en",
        notes=(
            "PERKESO's EIS benefits CLAIMS/application process page — deliberately "
            "tagged 'legal' not 'epf' (this is the claims procedure, distinct from "
            "the employer-registration facts tagged 'epf' above)."
        ),
    ),

    # ── tax incentives (Pioneer Status / ITA / RA — statutory, not grant_database) ──
    # Confirmed real via WebSearch (returned live content snippets: "Pioneer
    # Status (PS) provides income tax exemption of 70%-100% of statutory
    # income for 5 to 10 years"; "Investment Tax Allowance (ITA) offers an
    # allowance of 60%-100% on qualifying capital expenditure") — but NOT
    # content-verified via a direct fetch, same sandbox-egress restriction
    # as the property/business/epf/legal sources above (mida.gov.my is
    # blocked by this environment's network egress proxy, not a site
    # issue). Deliberately routed into document_chunks (RAG), not
    # grant_database: Pioneer Status/ITA/RA are percentage-of-income /
    # percentage-of-capex statutory tax reliefs, not fixed-MYR-band grants —
    # grant_database's amount_min_myr/amount_max_myr schema doesn't fit
    # them, and forcing a numeric "amount" would mean guessing a figure
    # that isn't actually what the incentive grants. RAG lets chat/agents
    # answer questions about them with a real citation instead.
    Source(
        name="mida-tax-incentives-overview",
        url="https://www.mida.gov.my/setting-up-content/incentives/",
        kind="html",
        domain="tax",
        ministry="Malaysian Investment Development Authority (MIDA)",
        language="en",
        notes=(
            "Pioneer Status and Investment Tax Allowance (ITA) overview — "
            "exemption/allowance percentages and duration under the Promotion "
            "of Investments Act 1986."
        ),
    ),
    Source(
        name="mida-reinvestment-allowance",
        url="https://www.mida.gov.my/setting-up-content/expand-and-diversify/",
        kind="html",
        domain="tax",
        ministry="Malaysian Investment Development Authority (MIDA)",
        language="en",
        notes=(
            "Reinvestment Allowance (RA) — incentive for existing companies "
            "expanding, modernising, or diversifying manufacturing/processing "
            "activity, under Schedule 7A of the Income Tax Act 1967."
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
