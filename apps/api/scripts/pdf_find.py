#!/usr/bin/env python3
"""Read-only: download a PDF and print the text around phrases (case-insensitive).

For checking what an official document actually says before a source is registered or a
figure is hard-coded. Writes nothing.

    python -m scripts.pdf_find URL "phrase one" "phrase two" [--context 700] [--max-hits 4]
"""
from __future__ import annotations

import argparse
import io
import re
import sys


def extract_pages(data: bytes) -> list[str]:
    from pypdf import PdfReader

    return [(page.extract_text() or "") for page in PdfReader(io.BytesIO(data)).pages]


def find_hits(pages: list[str], phrase: str, context: int, max_hits: int) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    pattern = re.compile(re.escape(phrase), re.IGNORECASE)
    for number, text in enumerate(pages, start=1):
        for match in pattern.finditer(text):
            start, end = max(0, match.start() - context // 3), min(len(text), match.end() + context)
            hits.append((number, " ".join(text[start:end].split())))
            if len(hits) >= max_hits:
                return hits
    return hits


def main() -> int:
    import httpx

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("phrases", nargs="+")
    parser.add_argument("--context", type=int, default=700)
    parser.add_argument("--max-hits", type=int, default=4)
    args = parser.parse_args()

    if not re.match(r"^https://[a-z0-9.-]+\.gov\.my/", args.url):
        print("only https://*.gov.my URLs are allowed", file=sys.stderr)
        return 2
    response = httpx.get(args.url, follow_redirects=True, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    pages = extract_pages(response.content)
    print(f"{args.url}: {len(pages)} pages, {sum(len(p) for p in pages)} chars")
    for phrase in args.phrases:
        hits = find_hits(pages, phrase, args.context, args.max_hits)
        print(f"\n=== {phrase!r}: {len(hits)} hit(s)")
        for number, snippet in hits:
            print(f"--- page {number}\n{snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
