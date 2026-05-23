"""Fetch sample documents from real Malaysian government sources.

Outputs raw text files to scripts/ingest/data/raw/ using the naming
convention:  {domain}_{slug}.txt

Run:
    python scripts/ingest/fetch_gov_docs.py
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

import httpx
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NakTahuBot/1.0; "
        "+https://github.com/timothylee58/tanya-chatbot-my)"
    ),
    "Accept-Language": "ms,en;q=0.9",
}

TIMEOUT = httpx.Timeout(30.0)


class Source(NamedTuple):
    domain: str
    slug: str
    url: str
    ministry: str
    selectors: list[str]  # CSS selectors to extract body text


SOURCES: list[Source] = [
    # ---------- FINANCE : LHDN (Inland Revenue Board) ----------
    Source(
        domain="finance",
        slug="lhdn_individual_tax_faq",
        url="https://www.hasil.gov.my/en/individual/individual-faq/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content", "#content", "body"],
    ),
    Source(
        domain="finance",
        slug="lhdn_efiling_guide",
        url="https://www.hasil.gov.my/en/individual/income-tax-individual/",
        ministry="Lembaga Hasil Dalam Negeri Malaysia",
        selectors=["main", "article", ".content", "#content", "body"],
    ),
    # ---------- FINANCE : EPF (KWSP) ----------
    Source(
        domain="finance",
        slug="epf_withdrawal_overview",
        url="https://www.kwsp.gov.my/en/member/withdrawal",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", "article", ".page-content", ".content-area", "body"],
    ),
    Source(
        domain="finance",
        slug="epf_contribution_rates",
        url="https://www.kwsp.gov.my/en/employer/contribution/contribution-rate",
        ministry="Kumpulan Wang Simpanan Pekerja",
        selectors=["main", "article", ".page-content", ".content-area", "body"],
    ),
    # ---------- GOVERNMENT : SSM ----------
    Source(
        domain="government",
        slug="ssm_business_registration",
        url="https://www.ssm.com.my/Pages/Quick_Reference/Business_Registration.aspx",
        ministry="Suruhanjaya Syarikat Malaysia",
        selectors=["main", ".ms-rtestate-field", ".content", "article", "body"],
    ),
    Source(
        domain="government",
        slug="ssm_company_registration",
        url="https://www.ssm.com.my/Pages/Quick_Reference/Company_Registration.aspx",
        ministry="Suruhanjaya Syarikat Malaysia",
        selectors=["main", ".ms-rtestate-field", ".content", "article", "body"],
    ),
    # ---------- HEALTH : MOH ----------
    Source(
        domain="health",
        slug="moh_public_health_services",
        url="https://www.moh.gov.my/index.php/pages/view/43",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="health",
        slug="moh_hospital_services",
        url="https://www.moh.gov.my/index.php/pages/view/2",
        ministry="Kementerian Kesihatan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    # ---------- EDUCATION : KPM ----------
    Source(
        domain="education",
        slug="kpm_education_system",
        url="https://www.moe.gov.my/en/dasar/dasar-pendidikan-kebangsaan",
        ministry="Kementerian Pendidikan Malaysia",
        selectors=["main", ".content", "article", "#main-content", "body"],
    ),
    Source(
        domain="education",
        slug="jpa_scholarship_guide",
        url="https://www.jpa.gov.my/en/perkhidmatan/biasiswa",
        ministry="Jabatan Perkhidmatan Awam",
        selectors=["main", ".content", "article", "#content", "body"],
    ),
    # ---------- LEGAL : KPKT / JPJ ----------
    Source(
        domain="legal",
        slug="jpj_road_tax_renewal",
        url="https://www.jpj.gov.my/en/web/main-site/cukai-jalan",
        ministry="Jabatan Pengangkutan Jalan",
        selectors=["main", ".content", "article", "#content", "body"],
    ),
    Source(
        domain="government",
        slug="myeg_government_services",
        url="https://www.myeg.com.my/services",
        ministry="Malaysia e-Government Services",
        selectors=["main", ".content", "article", ".services-list", "body"],
    ),
]


def _extract_text(html: str, selectors: list[str]) -> str:
    """Return clean text from the first matching CSS selector."""
    soup = BeautifulSoup(html, "lxml")

    # Remove navigation, headers, footers, scripts, styles
    for tag in soup(["nav", "header", "footer", "script", "style", "noscript"]):
        tag.decompose()

    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            return _clean(el.get_text(separator="\n"))

    return _clean(soup.get_text(separator="\n"))


def _clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def fetch_source(client: httpx.Client, source: Source) -> bool:
    out_path = RAW_DIR / f"{source.domain}_{source.slug}.txt"
    try:
        resp = client.get(source.url, follow_redirects=True)
        resp.raise_for_status()
        text = _extract_text(resp.text, source.selectors)

        if len(text) < 200:
            print(f"  [WARN] {source.slug}: extracted text too short ({len(text)} chars), skipping")
            return False

        # Prepend metadata header so the chunker can recover it
        header = (
            f"SOURCE_TITLE: {source.slug.replace('_', ' ').title()}\n"
            f"SOURCE_URL: {source.url}\n"
            f"MINISTRY: {source.ministry}\n"
            f"DOMAIN: {source.domain}\n"
            "---\n"
        )
        out_path.write_text(header + text, encoding="utf-8")
        print(f"  [OK]   {source.slug} → {out_path.name} ({len(text):,} chars)")
        return True

    except Exception as exc:
        print(f"  [ERR]  {source.slug}: {exc}")
        return False


def main() -> None:
    print(f"Fetching {len(SOURCES)} Malaysian government sources…\n")
    ok = 0
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT) as client:
        for source in SOURCES:
            print(f"→ {source.url}")
            if fetch_source(client, source):
                ok += 1
            time.sleep(1.5)  # polite delay

    print(f"\nDone: {ok}/{len(SOURCES)} sources saved to {RAW_DIR}")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
