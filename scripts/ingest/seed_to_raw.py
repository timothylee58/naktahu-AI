"""Convert seed CSVs to raw .txt files compatible with chunk_and_embed.py.

Maps seed CSV columns (content, dataset, year, ministry, url, source_title)
into the standard raw file format with SOURCE_TITLE / SOURCE_URL / etc. headers.

Run:
    python scripts/ingest/seed_to_raw.py
"""
from __future__ import annotations

import csv
from pathlib import Path

try:  # works both as `python scripts/ingest/seed_to_raw.py` and `-m`
    from scripts.ingest.metadata import most_recent_effective_date
except ImportError:  # pragma: no cover - script run with scripts/ingest on sys.path
    from metadata import most_recent_effective_date

SEED_DIR = Path(__file__).parent / "seed"
RAW_DIR = Path(__file__).parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Map seed CSV filename prefix → domain + expiry_aware flag
CSV_DOMAIN_MAP = {
    "lhdn_tax":        ("tax",         False),
    "kwsp_epf":        ("epf",         False),
    "ssm_business":    ("business",    False),
    "kpm_education":   ("education",   False),
    "moh_health":      ("healthcare",  True),
    "imi_immigration": ("immigration", True),
    "dosm_statistics": ("business",    False),  # DOSM macro stats — GDP/trade/labour map to business
}


def convert(csv_path: Path, domain: str, expiry_aware: bool) -> int:
    rows = []
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)

    if not rows:
        return 0

    # Group all rows for this CSV into a single raw file
    out_path = RAW_DIR / f"{domain}_{csv_path.stem}.txt"

    # Use first row's metadata for the file header
    first = rows[0]
    ministry = first.get("ministry", "Unknown")
    source_url = first.get("url", "")
    source_title = first.get("source_title", csv_path.stem.replace("_", " ").title())

    # Derive effective_date from the most recent `year` present so freshness
    # signals (analyst_node / temporal_accuracy) reflect the data's vintage.
    effective_date = most_recent_effective_date(row.get("year") for row in rows) or ""

    header = (
        f"SOURCE_TITLE: {source_title}\n"
        f"SOURCE_URL: {source_url}\n"
        f"MINISTRY: {ministry}\n"
        f"DOMAIN: {domain}\n"
        f"SOURCE_DATE: \n"
        f"EXPIRY_AWARE: {str(expiry_aware).lower()}\n"
        f"EFFECTIVE_DATE: {effective_date}\n"
        "---\n"
    )

    body_parts = []
    for row in rows:
        content = row.get("content", "").strip()
        dataset = row.get("dataset", "")
        if dataset and dataset not in content:
            body_parts.append(f"## {dataset}\n{content}")
        elif content:
            body_parts.append(content)

    body = "\n\n".join(body_parts)
    out_path.write_text(header + body, encoding="utf-8")
    return len(rows)


def main() -> None:
    total = 0
    for csv_path in sorted(SEED_DIR.glob("*.csv")):
        key = csv_path.stem
        if key not in CSV_DOMAIN_MAP:
            print(f"  [SKIP] {csv_path.name} — no domain mapping")
            continue
        domain, expiry_aware = CSV_DOMAIN_MAP[key]
        count = convert(csv_path, domain, expiry_aware)
        print(f"  [OK]   {csv_path.name} → {domain} ({count} rows){' [expiry_aware]' if expiry_aware else ''}")
        total += count
    print(f"\nConverted {total} rows → {RAW_DIR}")


if __name__ == "__main__":
    main()
