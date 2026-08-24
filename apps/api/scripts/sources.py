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
by migration 027, further widened by migration 030, and by migration 037
(Trap #6: government, education, legal, finance, healthcare, epf, tax,
business, immigration, culture, parliament, property, welfare) — never
invent a new one here. URLs must be real, verified pages; never guess a
feed URL.

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

    # ── government (cost-of-living / social assistance — Ihsan MADANI) ─────
    # Confirmed real via WebSearch: the official one-stop portal for social
    # welfare/cost-of-living assistance under the National Cost of Living
    # Action Council (NACCOL), Ministry of Domestic Trade and Cost of Living
    # (KPDN) — cross-referenced against malaysia.gov.my's own "low-income
    # families" persona page linking to this exact domain, not a lookalike.
    # NOT content-verified via a direct fetch — this sandbox's network
    # egress proxy returns EGRESS_BLOCKED for ihsanmadani.gov.my specifically
    # (confirmed via both curl and WebFetch this session), same restriction
    # documented for the property/business/epf/legal/tax sources above.
    # Classified "government" (general civic-assistance portal spanning
    # several programme types — electricity rebates, food aid, education
    # financing, entrepreneurship grants) rather than a narrower domain like
    # "finance" or "business", since no single one of those covers the
    # portal's actual scope.
    Source(
        name="ihsan-madani-home",
        url="https://ihsanmadani.gov.my/",
        kind="html",
        domain="welfare",
        ministry="National Cost of Living Action Council (NACCOL) / KPDN",
        language="bm",
        notes="Ihsan MADANI portal homepage — entry point for the full assistance catalogue.",
    ),
    Source(
        name="ihsan-madani-inisiatif",
        url="https://ihsanmadani.gov.my/inisiatif",
        kind="html",
        domain="welfare",
        ministry="National Cost of Living Action Council (NACCOL) / KPDN",
        language="bm",
        notes=(
            "Index of assistance initiatives across categories (education, "
            "income/entrepreneurship, housing, utilities) — the main listing "
            "page RAG needs for cross-programme questions."
        ),
    ),
    # These two category segments ("pendapatan", "pendidikan") are the only
    # two independently corroborated by this repo's own earlier WebSearch
    # results (/inisiatif/pendapatan/inisiatif-pendapatan-rakyat-ipr and
    # /inisiatif/pendidikan/program-sulung both came back as real, indexed
    # scheme-detail URLs, not just from a user-supplied description) — the
    # user reported these as the two highest-volume categories (income and
    # education) but also named 6 more category segments (Perumahan,
    # Utiliti, Pengangkutan, etc.) that have no independent corroboration
    # here. Deliberately NOT adding those 6: a plausible-looking but wrong
    # slug is a silently broken source entry, not a harmless guess, on a
    # page whose whole job is aggregating real citations.
    Source(
        name="ihsan-madani-pendapatan",
        url="https://ihsanmadani.gov.my/inisiatif/pendapatan",
        kind="html",
        domain="welfare",
        ministry="National Cost of Living Action Council (NACCOL) / KPDN",
        language="bm",
        notes="Income/entrepreneurship assistance category listing (IPR, INTAN, INSAN, IKHSAN and similar schemes).",
    ),
    Source(
        name="ihsan-madani-pendidikan",
        url="https://ihsanmadani.gov.my/inisiatif/pendidikan",
        kind="html",
        domain="welfare",
        ministry="National Cost of Living Action Council (NACCOL) / KPDN",
        language="bm",
        notes="Education assistance category listing (Program SULUNG and similar financing/exemption schemes).",
    ),
    Source(
        name="ihsan-madani-faq",
        url="https://ihsanmadani.gov.my/faq",
        kind="html",
        domain="welfare",
        ministry="National Cost of Living Action Council (NACCOL) / KPDN",
        language="bm",
        notes="Official FAQ — eligibility/registration process questions (eKasih linkage, how to check status).",
    ),

    # ── education domain — first-ever entries ──────────────────────────────
    # Registered zero sources until now (confirmed by grep before adding
    # these), despite study_agent/nodes.py's explain_node and
    # generate_quiz_node both calling query_rag_findings(..., "education",
    # ...) on every request — the agent has been architecturally live with
    # no real content backing it, silently degrading to citation-less
    # LLM-only answers. Found via WebSearch (this sandbox blocks direct
    # fetch to moe.gov.my/lp.moe.gov.my, confirmed again when trying —
    # EGRESS_BLOCKED via WebFetch, curl CONNECT tunnel 403), same
    # not-content-verified caveat as the property/business/epf/legal
    # entries above. All five are Lembaga Peperiksaan Malaysia (LPM) —
    # the statutory exam board under KPM, not a third-party exam-prep site.
    Source(
        name="lpm-spm-overview",
        url="https://lp.moe.gov.my/index.php/peperiksaan-pentaksiran/peringkat-menengah-atas/sijil-pelajaran-malaysia-spm",
        kind="html",
        domain="education",
        ministry="Lembaga Peperiksaan Malaysia (LPM) / Kementerian Pendidikan Malaysia (KPM)",
        language="bm",
        notes="Official SPM overview — structure, subjects, assessment components.",
    ),
    Source(
        name="lpm-makluman-spm",
        url="https://lp.moe.gov.my/index.php/makluman-spm",
        kind="html",
        domain="education",
        ministry="Lembaga Peperiksaan Malaysia (LPM) / Kementerian Pendidikan Malaysia (KPM)",
        language="bm",
        notes="Official SPM announcements index — the actual source of truth for exam-cycle changes, not a third-party recap.",
    ),
    Source(
        name="lpm-takwim-pentaksiran-2026",
        url="https://lp.moe.gov.my/index.php/makluman-spm/1405-takwim-pentaksiran-pusat-tingkatan-5-peperiksaan-sijil-pelajaran-malaysia-spm-tahun-2026-dan-tingkatan-4-peperiksaan-spm-tahun-2027",
        kind="html",
        domain="education",
        ministry="Lembaga Peperiksaan Malaysia (LPM) / Kementerian Pendidikan Malaysia (KPM)",
        language="bm",
        notes="Central-assessment calendar for Form 5 SPM 2026 and Form 4 SPM 2027 candidates.",
    ),
    Source(
        name="lpm-jadual-waktu-spmu-2026",
        url="https://lp.moe.gov.my/index.php/jadual-waktu/1436-jadual-waktu-peperiksaan-sijil-pelajaran-malaysia-ulangan-spmu-2026ngan-2026",
        kind="html",
        domain="education",
        ministry="Lembaga Peperiksaan Malaysia (LPM) / Kementerian Pendidikan Malaysia (KPM)",
        language="bm",
        notes="SPM Ulangan (repeat/resit) 2026 exam timetable page.",
    ),
    Source(
        name="lpm-home",
        url="https://lp.moe.gov.my/",
        kind="html",
        domain="education",
        ministry="Lembaga Peperiksaan Malaysia (LPM) / Kementerian Pendidikan Malaysia (KPM)",
        language="bm",
        notes="LPM portal home — general exam-board contact/structure info, catch-all for queries the more specific pages above don't cover.",
    ),
    # Registered from a user-supplied source (URL + the official PDF itself,
    # "JWP_SPM_2026_18_OGOS_2026.pdf"), not found via WebSearch — this one IS
    # content-verified: pdftotext was run directly against the PDF in this
    # session and confirmed a real LPM/KPM "Jadual Waktu Peperiksaan SPM 2026"
    # document (spoken/oral papers 26–29 Oct and 2–5 Nov 2026; written papers
    # 23 Nov–17 Dec 2026). Distinct from lpm-jadual-waktu-spmu-2026 above,
    # which is the SPM *Ulangan* (resit) 2026 timetable — a different exam
    # cycle, different candidates, different page.
    Source(
        name="lpm-jadual-waktu-spm-2026",
        url="https://lp.moe.gov.my/index.php/jw-spm/1447-jadual-waktu-peperiksaan-sijil-pelajaran-malaysia-2026",
        kind="html",
        domain="education",
        ministry="Lembaga Peperiksaan Malaysia (LPM) / Kementerian Pendidikan Malaysia (KPM)",
        language="bm",
        notes=(
            "SPM 2026 (regular, non-resit) exam timetable. Content-verified via "
            "the official JWP SPM 2026 PDF: oral/speaking-listening tests 26-29 "
            "Oct and 2-5 Nov 2026; written papers 23 Nov-17 Dec 2026."
        ),
    ),

    # ── First registrations for 5 domains that had ZERO sources ─────────────
    # government/finance/healthcare/immigration/culture — found via WebSearch,
    # confirmed as real official ministry domains (.gov.my, verified against
    # each ministry's own name, not a lookalike). Same not-content-verified
    # caveat as every other WebSearch-found entry in this file: this sandbox
    # blocks direct fetch to all of these (re-confirmed — WebFetch/curl both
    # 403 on malaysia.gov.my, mof.gov.my, moh.gov.my, imi.gov.my, motac.gov.my).
    # Two pages per domain: the general portal (broad coverage, catch-all) and
    # one topic-specific page (the thing people actually search for).
    Source(
        name="mygovernment-portal-home",
        url="https://www.malaysia.gov.my/en",
        kind="html",
        domain="government",
        ministry="MyGovernment / National Digital Department (JDN)",
        language="en",
        notes="Central government-services directory — the single broadest 'which agency handles X' catch-all.",
    ),
    Source(
        name="mygovernment-services-noncitizen",
        url="https://rai.malaysia.gov.my/digital-services/apply---i-services-registration-service-provider--user",
        kind="html",
        domain="government",
        ministry="MyGovernment / National Digital Department (JDN)",
        language="en",
        notes="Non-citizen-facing government services index (immigration/employment/education/healthcare cross-references).",
    ),
    Source(
        name="mof-portal-home",
        url="https://www.mof.gov.my/portal/en",
        kind="html",
        domain="finance",
        ministry="Kementerian Kewangan Malaysia (MOF)",
        language="en",
        notes="MOF official portal — fiscal/tax policy, budget announcements, exemption guidelines.",
    ),
    Source(
        name="mof-belanjawan-portal",
        url="https://belanjawan.mof.gov.my/en",
        kind="html",
        domain="finance",
        ministry="Kementerian Kewangan Malaysia (MOF)",
        language="en",
        notes="Federal Budget portal — Budget Speech text, fiscal outlook, revenue/expenditure estimates.",
    ),
    Source(
        name="moh-portal-home",
        url="https://www.moh.gov.my/en",
        kind="html",
        domain="healthcare",
        ministry="Kementerian Kesihatan Malaysia (KKM)",
        language="en",
        notes="MOH official portal — public health programmes, facility directory.",
    ),
    Source(
        name="moh-directory",
        url="https://www.moh.gov.my/en/directory",
        kind="html",
        domain="healthcare",
        ministry="Kementerian Kesihatan Malaysia (KKM)",
        language="en",
        notes="Government clinic/hospital directory — the actual 'where do I go' lookup, not just ministry-org info.",
    ),
    Source(
        name="imi-portal-home",
        url="https://www.imi.gov.my/index.php/en/home/",
        kind="html",
        domain="immigration",
        ministry="Jabatan Imigresen Malaysia (JIM)",
        language="en",
        notes="Immigration Department official portal home.",
    ),
    Source(
        name="imi-visa-services",
        url="https://www.imi.gov.my/index.php/en/main-services/visa/",
        kind="html",
        domain="immigration",
        ministry="Jabatan Imigresen Malaysia (JIM)",
        language="en",
        notes="Visa services page — pass/permit types, the highest-volume immigration query category.",
    ),
    Source(
        name="motac-portal-home",
        url="https://www.motac.gov.my/en/",
        kind="html",
        domain="culture",
        ministry="Kementerian Pelancongan, Kesenian dan Kebudayaan (MOTAC)",
        language="en",
        notes="MOTAC official portal — tourism/arts/culture/heritage/museum/archives remit.",
    ),
    Source(
        name="motac-policy",
        url="https://www.motac.gov.my/en/profile/policy",
        kind="html",
        domain="culture",
        ministry="Kementerian Pelancongan, Kesenian dan Kebudayaan (MOTAC)",
        language="en",
        notes="Ministry policy page — heritage-designation and cultural-preservation policy specifics.",
    ),

    # ── "Edisi Kemerdekaan" seasonal AI lens (Aug25-Sep20) — the two
    # sub-topics that have a real, verifiable official source today: 1957
    # Merdeka history and MA63 (Malaysia Day). Both found via WebSearch on
    # confirmed .gov.my domains (Arkib Negara, JPM/BHESS, MyGOV) — same
    # not-content-verified caveat as every other WebSearch-found entry here.
    # Deliberately NOT registering parade-logistics or JPJ-discount
    # sources for this lens: no real official source was found for either
    # in this session, and inventing one would violate this file's own
    # "URLs must be real, verified pages; never guess" rule — the frontend
    # lens surfaces only the sub-topics that have sources.
    Source(
        name="arkib-pengisytiharan-kemerdekaan",
        url="https://pustakailmu.arkib.gov.my/index.php/ms/pustaka-ilmu/imbasan-fakta/dokumen-perisytiharan-kemerdekaan",
        kind="html",
        domain="culture",
        ministry="Arkib Negara Malaysia (National Archives)",
        language="bm",
        notes="Official 31 Aug 1957 Proclamation of Independence document and its historical context.",
    ),
    Source(
        name="arkib-menjejaki-31-ogos-1957",
        url="https://pustakailmu.arkib.gov.my/index.php/ms/pustaka-ilmu/jendela-sejarah/menjejaki-31-ogos-1957",
        kind="html",
        domain="culture",
        ministry="Arkib Negara Malaysia (National Archives)",
        language="bm",
        notes="Narrative history of the 31 Aug 1957 independence ceremony at Stadium Merdeka.",
    ),
    Source(
        name="bhess-perjanjian-ma63",
        url="https://bhess.jpm.gov.my/index.php/perjanjian-ma63/",
        kind="html",
        domain="culture",
        ministry="Bahagian Hal Ehwal Sabah & Sarawak (BHESS), Jabatan Perdana Menteri (JPM)",
        language="bm",
        notes="Official JPM page on the Malaysia Agreement 1963 (MA63) — the Hari Malaysia / 16 Sep source.",
    ),
    Source(
        name="mygov-rukun-negara",
        url="https://www.malaysia.gov.my/portal/content/30110?language=my",
        kind="html",
        domain="culture",
        ministry="MyGovernment Portal (MAMPU)",
        language="bm",
        notes="Official Rukun Negara text — the 5 national principles and their formation context (est. 1970).",
    ),

    # ── "Who's my MP" knowledge expansion — the `parliament` domain had ZERO
    # registered sources despite already having a full Hansard
    # speeches/votes pipeline (scripts/ingest_parliament/), a mp_profiles
    # schema (migration 025), and read endpoints (routers/parliament.py) —
    # what it never had was a source that actually answers "who is my MP",
    # since nothing seeds mp_profiles with the 222-constituency roster in
    # the first place. Two complementary sources, not duplicates: MyMP is
    # the constituency-lookup/roster/bio source (who represents me); the
    # Parliament portal is the speeches/bills/voting-history source the
    # existing Hansard pipeline already scrapes from, registered here so
    # it's finally visible to check_domain_coverage.py and
    # ingest-sources.yml instead of living only inside a separate,
    # never-run pipeline script.
    Source(
        name="mymp-portal-home",
        url="https://mymp.org.my/",
        kind="html",
        domain="parliament",
        ministry="MyMP (MCCHR — Malaysian Centre for Constitutionalism and Human Rights; civil-society, NOT a government body)",
        language="en",
        notes=(
            "Constituency-to-MP lookup and MP biographies for all 222 Dewan Rakyat "
            "seats — exactly the 'who is my MP' gap. Ministry field is deliberately "
            "labelled non-governmental: this must never be cited or badged as an "
            "official .gov.my source. Found via WebSearch, confirmed as the real "
            "MyMP/MCCHR project (not a lookalike domain) but not content-verified "
            "via direct fetch in this sandbox."
        ),
    ),
    Source(
        name="parlimen-hansard-dewan-rakyat",
        url="https://www.parlimen.gov.my/hansard-dewan-rakyat.html",
        kind="html",
        domain="parliament",
        ministry="Parlimen Malaysia",
        language="bm",
        notes=(
            "The same official Hansard index scripts/ingest_parliament/"
            "fetch_hansard.py already scrapes for speeches/bills/voting-history "
            "(that pipeline's own HANSARD_LIST_URL) — registered here so this "
            "domain's real content source is visible in this catalog and to "
            "check_domain_coverage.py, not only inside that separate script. "
            "Confirmed reachable per fetch_hansard.py's own Trap #11 note "
            "(parlimen.gov.my is unreachable from THIS sandbox specifically, "
            "proxy-blocked, not a dead URL)."
        ),
    ),

    # ── DOSM (Department of Statistics Malaysia) + KPDN (Ministry of
    # Domestic Trade and Cost of Living) + one more SSM page — multi-domain
    # knowledge-base expansion. URLs confirmed real via WebSearch (dosm.gov.my,
    # open.dosm.gov.my, kpdn.gov.my, ssm.com.my all resolved to the actual
    # official portals, not lookalikes) but NOT content-verified via direct
    # fetch — same sandbox-egress restriction as every other WebSearch-found
    # entry in this file (see module docstring). DOSM's own statistics span
    # population, economic, and social data with no single narrower domain
    # fitting all of it, so — like mygovernment-portal-home — it's tagged
    # "government" rather than "finance". KPDN's own portal is tagged
    # "business" (trade-licensing/consumer-protection remit); its
    # cost-of-living assistance programme is already covered separately by
    # the "welfare"-tagged Ihsan MADANI entries above, which KPDN also runs.
    Source(
        name="dosm-portal-home",
        url="https://www.dosm.gov.my/",
        kind="html",
        domain="government",
        ministry="Jabatan Perangkaan Malaysia (DOSM)",
        language="en",
        notes="National statistics department's official portal — population, economic, and social statistics catalogue.",
    ),
    Source(
        name="opendosm-home",
        url="https://open.dosm.gov.my/",
        kind="html",
        domain="government",
        ministry="Jabatan Perangkaan Malaysia (DOSM)",
        language="en",
        notes="OpenDOSM — DOSM's open-data catalogue/dashboard platform (CPI, GDP, population, labour force series).",
    ),
    Source(
        name="kpdn-portal-home",
        url="https://www.kpdn.gov.my/en/home",
        kind="html",
        domain="business",
        ministry="Kementerian Perdagangan Dalam Negeri dan Kos Sara Hidup (KPDN)",
        language="en",
        notes="Ministry of Domestic Trade and Cost of Living official portal — trade licensing, consumer protection, price-control enforcement.",
    ),
    Source(
        name="ssm-ezbiz-online",
        url="https://www.ssm.com.my/Pages/Services/Registration-of-Business-(ROB)/EzBiz-Online.aspx",
        kind="html",
        domain="business",
        ministry="Suruhanjaya Syarikat Malaysia (SSM)",
        language="en",
        notes="Official explainer page for EzBiz, SSM's online sole-proprietorship/partnership registration, renewal, and termination service.",
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
