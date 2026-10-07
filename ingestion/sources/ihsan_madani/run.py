"""CLI entrypoint — scrape Ihsan MADANI, write clean JSON. Does not touch
Supabase or pgvector; that's a separate mapping step (see scraper.py's
module docstring).

Usage:
    python -m ingestion.sources.ihsan_madani.run [--out schemes.json] [--category umum kesihatan ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .scraper import CATEGORIES, scrape_all


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="ingestion/sources/ihsan_madani/output.json")
    parser.add_argument("--category", nargs="*", choices=CATEGORIES, default=None)
    args = parser.parse_args()

    try:
        records = scrape_all(categories=args.category)
    except RuntimeError as exc:
        print(f"Aborted: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps([r.model_dump(mode="json") for r in records], indent=2, ensure_ascii=False)
    )
    print(f"Wrote {len(records)} scheme records to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
