"""Fetch documents from real Malaysian government sources.

Outputs raw text files to scripts/ingest/data/raw/ using the naming
convention:  {domain}_{slug}.txt

Run:
    python scripts/ingest/fetch_gov_docs.py
    python scripts/ingest/fetch_gov_docs.py --domain tax        # single domain
    python scripts/ingest/fetch_gov_docs.py --dry-run           # list URLs only
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import NamedTuple

# ── Authoritative domain → URL map (used by ingestion tooling) ───────────────
DOMAIN_SOURCES: dict[str, list[str]] = {
    "tax": [
        "https://www.hasil.gov.my/en/individual/individual-faq/",
        "https://www.hasil.gov.my/en/individual/individual-life-cycle/how-to-declare-income/tax-relief/",
        "https://www.lhdn.gov.my/en/penalty-and-offences/",
    ],
    "epf": [
        "https://www.kwsp.gov.my/en/member/withdrawal",
        "https://www.kwsp.gov.my/en/employer/contribution/contribution-rate",
        "https://www.kwsp.gov.my/en/member/about-epf/epf-account-restructuring",
    ],
    "business": [
        "https://www.ssm.com.my/Pages/Quick_Reference/Business_Registration.aspx",
        "https://www.hasil.gov.my/en/e-invoice/",
        "https://mysst.customs.gov.my/",
    ],
    "education": [
        "https://www.ptptn.gov.my/",
        "https://www.jpa.gov.my/en/perkhidmatan/biasiswa",
        "https://www.moe.gov.my/en/dasar/",
    ],
    "healthcare": [
        "https://www.moh.gov.my/index.php/pages/view/43",
        "https://portal.moh.gov.my/",
    ],
    "immigration": [
        "https://www.imi.gov.my/index.php/en/main-services/visa",
        "https://www.imi.gov.my/index.php/en/main-services/long-term-pass",
        "https://www.mm2h.gov.my/",
    ],
}

# Chunk size per domain — tax tables and healthcare advisories chunk smaller
DOMAIN_CHUNK_SIZES: dict[str, int] = {
    "tax": 256,
    "epf": 512,
    "business": 512,
    "education": 512,
    "healthcare": 256,
    "immigration": 512,
}

# Domains whose content is time-sensitive and should be tagged expiry_aware
EXPIRY_AWARE_DOMAINS: frozenset[str] = frozenset({"healthcare", "immigration"})

import httpx
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NakTahuBot/1.0; "
        "+https://github.com/timothylee58/naktahu-AI)"
    ),
    "Accept-Language": "ms,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIMEOUT = httpx.Timeout(30.0)
POLITE_DELAY = 2.0  # seconds between requests


class Source(NamedTuple):
    domain: str
    slug: str
    url: str
    ministry: str
    selectors: list[str]


SOURCES: list[Source] = [
    # ─────────────────────────────────────────────────────────────────
    # DOMAIN: tax  (Cukai & LHDN)
    # ─────────────────────────────────────────────────────────────────
    Source(
        domain="tax",
        slug="lhdn_individual_tax_rate",
        url="https://www.hasil.gov.my/en/individual/individual-life-cycle/how-to-declare-income/tax-rate/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", ".entry-content", "#content", "body"],
    ),
    Source(
        domain="tax",
        slug="lhdn_personal_tax_relief",
        url="https://www.hasil.gov.my/en/individual/individual-life-cycle/how-to-declare-income/tax-relief/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", ".entry-content", "#content", "body"],
    ),
    Source(
        domain="tax",
        slug="lhdn_filing_programme",
        url="https://www.hasil.gov.my/en/individual/individual-life-cycle/file-return-form/return-form-filing-programme/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", "#content", "body"],
    ),
    Source(
        domain="tax",
        slug="lhdn_efiling_guide",
        url="https://www.hasil.gov.my/en/individual/individual-life-cycle/file-return-form/how-to-file-tax-return/e-filing/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", "#content", "body"],
    ),
    Source(
        domain="tax",
        slug="lhdn_rpgt",
        url="https://www.hasil.gov.my/en/other-taxes/real-property-gains-tax/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", "#content", "body"],
    ),
    Source(
        domain="tax",
        slug="lhdn_stamp_duty",
        url="https://www.hasil.gov.my/en/stamp-duty/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", "#content", "body"],
    ),
    Source(
        domain="tax",
        slug="lhdn_corporate_tax",
        url="https://www.hasil.gov.my/en/company/company-life-cycle/how-to-declare-income/tax-rate/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", "#content", "body"],
    ),
    Source(
        domain="tax",
        slug="sst_registration",
        url="https://mysst.customs.gov.my/",
        ministry="Jabatan Kastam Diraja Malaysia",
        selectors=["main", ".content", "#mainContent", "article", "body"],
    ),
    Source(
        domain="tax",
        slug="lhdn_pcb_mtd",
        url="https://www.hasil.gov.my/en/individual/individual-life-cycle/how-to-declare-income/monthly-tax-deduction/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", "#content", "body"],
    ),
    Source(
        domain="tax",
        slug="lhdn_faq_individual",
        url="https://www.hasil.gov.my/en/individual/individual-faq/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", ".faq-content", "#content", "body"],
    ),

    # ─────────────────────────────────────────────────────────────────
    # DOMAIN: epf  (KWSP / EPF)
    # ─────────────────────────────────────────────────────────────────
    Source(
        domain="epf",
        slug="kwsp_contribution_rates",
        url="https://www.kwsp.gov.my/en/employer/contribution/contribution-rate",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", ".page-content", "article", ".content-area", "body"],
    ),
    Source(
        domain="epf",
        slug="kwsp_withdrawal_overview",
        url="https://www.kwsp.gov.my/en/member/withdrawal",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", ".page-content", "article", ".content-area", "body"],
    ),
    Source(
        domain="epf",
        slug="kwsp_housing_withdrawal",
        url="https://www.kwsp.gov.my/en/member/withdrawal/housing",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", ".page-content", "article", ".content-area", "body"],
    ),
    Source(
        domain="epf",
        slug="kwsp_education_withdrawal",
        url="https://www.kwsp.gov.my/en/member/withdrawal/education",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", ".page-content", "article", ".content-area", "body"],
    ),
    Source(
        domain="epf",
        slug="kwsp_health_withdrawal",
        url="https://www.kwsp.gov.my/en/member/withdrawal/health",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", ".page-content", "article", ".content-area", "body"],
    ),
    Source(
        domain="epf",
        slug="kwsp_account_restructuring",
        url="https://www.kwsp.gov.my/en/member/about-epf/epf-account-restructuring",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", ".page-content", "article", ".content-area", "body"],
    ),
    Source(
        domain="epf",
        slug="kwsp_i_invest",
        url="https://www.kwsp.gov.my/en/member/grow-your-savings/i-invest",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", ".page-content", "article", ".content-area", "body"],
    ),
    Source(
        domain="epf",
        slug="kwsp_member_faq",
        url="https://www.kwsp.gov.my/en/member/faq",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", ".page-content", "article", ".faq", "body"],
    ),

    # ─────────────────────────────────────────────────────────────────
    # DOMAIN: business  (Perniagaan & SSM)
    # ─────────────────────────────────────────────────────────────────
    Source(
        domain="business",
        slug="ssm_business_registration",
        url="https://www.ssm.com.my/Pages/Quick_Reference/Business_Registration.aspx",
        ministry="Suruhanjaya Syarikat Malaysia",
        selectors=["main", ".ms-rtestate-field", ".content", "article", "body"],
    ),
    Source(
        domain="business",
        slug="ssm_company_registration",
        url="https://www.ssm.com.my/Pages/Quick_Reference/Company_Registration.aspx",
        ministry="Suruhanjaya Syarikat Malaysia",
        selectors=["main", ".ms-rtestate-field", ".content", "article", "body"],
    ),
    Source(
        domain="business",
        slug="ssm_annual_return",
        url="https://www.ssm.com.my/Pages/Services/Electronic_Submissions/MBRS.aspx",
        ministry="Suruhanjaya Syarikat Malaysia",
        selectors=["main", ".ms-rtestate-field", ".content", "article", "body"],
    ),
    Source(
        domain="business",
        slug="smecorp_grants",
        url="https://www.smecorp.gov.my/index.php/en/programmes/2015-12-21-08-36-44/grant",
        ministry="Perbadanan Perusahaan Kecil dan Sederhana Malaysia",
        selectors=["main", ".itemFullText", ".content", "article", "body"],
    ),
    Source(
        domain="business",
        slug="mida_investment_guide",
        url="https://www.mida.gov.my/investor-s-guide/",
        ministry="Malaysian Investment Development Authority",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="business",
        slug="mdec_digital_grants",
        url="https://mdec.my/programmes/",
        ministry="Malaysia Digital Economy Corporation",
        selectors=["main", ".content", "article", ".programme-list", "body"],
    ),
    Source(
        domain="business",
        slug="miti_licences",
        url="https://www.miti.gov.my/index.php/pages/view/2",
        ministry="Kementerian Pelaburan, Perdagangan dan Industri",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="business",
        slug="hasil_business_income_tax",
        url="https://www.hasil.gov.my/en/company/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content-area", "#content", "body"],
    ),

    # ─────────────────────────────────────────────────────────────────
    # DOMAIN: education  (Pendidikan & SPM)
    # ─────────────────────────────────────────────────────────────────
    Source(
        domain="education",
        slug="moe_spm_info",
        url="https://www.moe.gov.my/en/pelajaran/peperiksaan/spm",
        ministry="Kementerian Pendidikan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="education",
        slug="mpm_stpm",
        url="https://www.mpm.edu.my/en/stpm/about-stpm",
        ministry="Majlis Peperiksaan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="education",
        slug="jpa_scholarship",
        url="https://www.jpa.gov.my/en/perkhidmatan/biasiswa",
        ministry="Jabatan Perkhidmatan Awam Malaysia",
        selectors=["main", ".content", "article", "#content", "body"],
    ),
    Source(
        domain="education",
        slug="ptptn_loan",
        url="https://www.ptptn.gov.my/",
        ministry="Perbadanan Tabung Pendidikan Tinggi Nasional",
        selectors=["main", ".content", "article", ".homepage-content", "body"],
    ),
    Source(
        domain="education",
        slug="upu_application",
        url="https://upu.mohe.gov.my/",
        ministry="Kementerian Pengajian Tinggi Malaysia",
        selectors=["main", ".content", "article", "#content", "body"],
    ),
    Source(
        domain="education",
        slug="mara_mrsm",
        url="https://www.mara.gov.my/en/education/mrsm/",
        ministry="Majlis Amanah Rakyat",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="education",
        slug="lppkn_education_loan",
        url="https://www.lppkn.gov.my/",
        ministry="Lembaga Penduduk dan Pembangunan Keluarga Negara",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="education",
        slug="mohe_private_universities",
        url="https://www.mohe.gov.my/en/students/private-higher-education",
        ministry="Kementerian Pengajian Tinggi Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),

    # ─────────────────────────────────────────────────────────────────
    # DOMAIN: health  (Kesihatan)
    # ─────────────────────────────────────────────────────────────────
    Source(
        domain="health",
        slug="moh_public_health",
        url="https://www.moh.gov.my/index.php/pages/view/43",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="health",
        slug="moh_hospital_list",
        url="https://www.moh.gov.my/index.php/pages/view/2",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="health",
        slug="moh_immunisation",
        url="https://www.moh.gov.my/index.php/pages/view/43",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="health",
        slug="kkm_chronic_disease",
        url="https://www.moh.gov.my/index.php/pages/view/3629",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="health",
        slug="mysejahtera",
        url="https://mysejahtera.malaysia.gov.my/",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", ".hero", "body"],
    ),
    Source(
        domain="health",
        slug="moh_mental_health",
        url="https://www.moh.gov.my/index.php/pages/view/286",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="health",
        slug="oku_jkm",
        url="https://www.jkm.gov.my/jkm/index.php?r=portal/content&id=2&lang=en",
        ministry="Jabatan Kebajikan Masyarakat",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="health",
        slug="moh_maternal_health",
        url="https://www.moh.gov.my/index.php/pages/view/170",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),

    # ─────────────────────────────────────────────────────────────────
    # DOMAIN: immigration  (Imigresen)
    # ─────────────────────────────────────────────────────────────────
    Source(
        domain="immigration",
        slug="imi_passport",
        url="https://www.imi.gov.my/index.php/en/main-services/passport",
        ministry="Jabatan Imigresen Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="immigration",
        slug="imi_visa_types",
        url="https://www.imi.gov.my/index.php/en/main-services/visa",
        ministry="Jabatan Imigresen Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="immigration",
        slug="imi_permanent_resident",
        url="https://www.imi.gov.my/index.php/en/main-services/permanent-resident",
        ministry="Jabatan Imigresen Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="immigration",
        slug="imi_employment_pass",
        url="https://esd.imi.gov.my/",
        ministry="Jabatan Imigresen Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="immigration",
        slug="imi_student_pass",
        url="https://www.imi.gov.my/index.php/en/main-services/student-pass",
        ministry="Jabatan Imigresen Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="immigration",
        slug="mm2h",
        url="https://www.mm2h.gov.my/",
        ministry="Kementerian Pelancongan dan Kebudayaan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="immigration",
        slug="jpn_mykad",
        url="https://www.jpn.gov.my/en/perkhidmatan/kad-pengenalan/",
        ministry="Jabatan Pendaftaran Negara Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="immigration",
        slug="imi_renunciation",
        url="https://www.imi.gov.my/index.php/en/main-services/citizenship",
        ministry="Jabatan Imigresen Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
]


def _extract_text(html: str, selectors: list[str]) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["nav", "header", "footer", "script", "style", "noscript", "aside"]):
        tag.decompose()

    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n")
            if len(text.strip()) > 200:
                return _clean(text)

    return _clean(soup.get_text(separator="\n"))


def _clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _parse_last_modified(resp: httpx.Response) -> str:
    """Return ISO date string from Last-Modified header, or empty string."""
    raw = resp.headers.get("last-modified", "")
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except Exception:
        return ""


def fetch_source(client: httpx.Client, source: Source) -> bool:
    out_path = RAW_DIR / f"{source.domain}_{source.slug}.txt"
    try:
        resp = client.get(source.url, follow_redirects=True)
        resp.raise_for_status()
        text = _extract_text(resp.text, source.selectors)

        if len(text) < 200:
            print(f"  [WARN] {source.slug}: text too short ({len(text)} chars)")
            return False

        source_date = _parse_last_modified(resp)
        expiry_aware = source.domain in EXPIRY_AWARE_DOMAINS

        header = (
            f"SOURCE_TITLE: {source.slug.replace('_', ' ').title()}\n"
            f"SOURCE_URL: {source.url}\n"
            f"MINISTRY: {source.ministry}\n"
            f"DOMAIN: {source.domain}\n"
            f"SOURCE_DATE: {source_date}\n"
            f"EXPIRY_AWARE: {str(expiry_aware).lower()}\n"
            "---\n"
        )
        out_path.write_text(header + text, encoding="utf-8")
        print(f"  [OK]   {source.slug} ({len(text):,} chars){' [expiry_aware]' if expiry_aware else ''}")
        return True

    except Exception as exc:
        print(f"  [ERR]  {source.slug}: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Malaysian government source documents")
    parser.add_argument(
        "--domain",
        choices=["tax", "epf", "business", "education", "health", "immigration"],
        help="Fetch only a specific domain",
    )
    parser.add_argument("--dry-run", action="store_true", help="List URLs without fetching")
    args = parser.parse_args()

    sources = SOURCES
    if args.domain:
        sources = [s for s in SOURCES if s.domain == args.domain]
    if not sources:
        print("No matching sources found.")
        sys.exit(1)

    if args.dry_run:
        for s in sources:
            print(f"[{s.domain:12}] {s.url}")
        print(f"\nTotal: {len(sources)} sources")
        return

    domain_counts: dict[str, tuple[int, int]] = {}
    print(f"Fetching {len(sources)} sources…\n")

    with httpx.Client(headers=HEADERS, timeout=TIMEOUT) as client:
        for i, source in enumerate(sources):
            print(f"[{i + 1}/{len(sources)}] {source.domain}/{source.slug}")
            ok = fetch_source(client, source)
            domain_counts.setdefault(source.domain, (0, 0))
            prev = domain_counts[source.domain]
            domain_counts[source.domain] = (prev[0] + (1 if ok else 0), prev[1] + 1)
            if i < len(sources) - 1:
                time.sleep(POLITE_DELAY)

    print("\n─── Summary ───────────────────────────────")
    total_ok = total = 0
    for domain, (ok, n) in sorted(domain_counts.items()):
        print(f"  {domain:12} {ok}/{n}")
        total_ok += ok
        total += n
    print(f"  {'TOTAL':12} {total_ok}/{total}")
    print(f"  Raw files: {RAW_DIR}")

    if total_ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
