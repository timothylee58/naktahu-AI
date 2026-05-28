"""Chunk raw text files and generate embeddings via ILMU API (OpenAI-compatible).

Reads  : scripts/ingest/data/raw/{domain}_{slug}.txt
Outputs: scripts/ingest/data/processed/chunks.jsonl

Each JSONL line contains:
  id, content, content_hash, language, domain, source_title, source_url,
  ministry, embedding, expiry_aware, source_date

Run:
    python scripts/ingest/chunk_and_embed.py
    python scripts/ingest/chunk_and_embed.py --domain tax
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

import pycld2
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent.parent / "apps" / "api" / ".env")

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_DIR = Path(__file__).parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "chunks.jsonl"

CHUNK_OVERLAP = 64
CHARS_PER_TOKEN = 4

# Per-domain chunk sizes — matches DOMAIN_CHUNK_SIZES in fetch_gov_docs.py
DOMAIN_CHUNK_SIZES: dict[str, int] = {
    "tax": 256,
    "epf": 512,
    "business": 512,
    "education": 512,
    "healthcare": 256,
    "immigration": 512,
}
DEFAULT_CHUNK_SIZE = 512

EMBED_BATCH = 50


HEADER_RE = re.compile(
    r"SOURCE_TITLE:[ \t]*(.+)\n"
    r"SOURCE_URL:[ \t]*(.+)\n"
    r"MINISTRY:[ \t]*(.+)\n"
    r"DOMAIN:[ \t]*(.+)\n"
    r"(?:SOURCE_DATE:[ \t]*([^\n]*)\n)?"
    r"(?:EXPIRY_AWARE:[ \t]*([^\n]*)\n)?"
    r"---\n",
)


def parse_header(raw: str) -> tuple[dict[str, str], str]:
    m = HEADER_RE.match(raw)
    if not m:
        raise ValueError("Missing metadata header in file")
    meta = {
        "source_title": m.group(1).strip(),
        "source_url": m.group(2).strip(),
        "ministry": m.group(3).strip(),
        "domain": m.group(4).strip(),
        "source_date": (m.group(5) or "").strip() or None,
        "expiry_aware": (m.group(6) or "").strip().lower() == "true",
    }
    body = raw[m.end():]
    return meta, body


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_language(text: str) -> str:
    try:
        _, _, best = pycld2.detect(text[:2000])
        lang_code = best[0][1]
        if lang_code in ("ms", "id"):
            return "bm"
        if lang_code in ("zh", "zh-Hant", "zh-Hans", "zh-TW", "zh-CN"):
            return "zh"
        return "en"
    except Exception:
        return "en"


def embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    model = (
        os.getenv("OPENAI_EMBEDDING_MODEL")
        or os.getenv("ILMU_EMBEDDING_MODEL")
        or "text-embedding-3-small"
    ).strip() or "text-embedding-3-small"
    resp = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in resp.data]


def chunk_file(path: Path, domain_filter: str | None) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    try:
        meta, body = parse_header(raw)
    except ValueError:
        parts = path.stem.split("_", 1)
        meta = {
            "source_title": path.stem.replace("_", " ").title(),
            "source_url": "",
            "ministry": "Unknown",
            "domain": parts[0] if parts else "government",
            "source_date": None,
            "expiry_aware": False,
        }
        body = raw

    if domain_filter and meta["domain"] != domain_filter:
        return []

    chunk_size = DOMAIN_CHUNK_SIZES.get(meta["domain"], DEFAULT_CHUNK_SIZE)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size * CHARS_PER_TOKEN,
        chunk_overlap=CHUNK_OVERLAP * CHARS_PER_TOKEN,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    records = []
    for chunk in splitter.split_text(body):
        chunk = chunk.strip()
        if len(chunk) < 80:
            continue
        records.append({
            "id": str(uuid.uuid4()),
            "content": chunk,
            "content_hash": content_hash(chunk),
            "language": detect_language(chunk),
            "domain": meta["domain"],
            "source_title": meta["source_title"],
            "source_url": meta["source_url"],
            "ministry": meta["ministry"],
            "expiry_aware": meta["expiry_aware"],
            "source_date": meta["source_date"],
            "embedding": None,
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", help="Process only this domain")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ILMU_API_KEY")
    # Only use ILMU base URL if falling back to ILMU key
    base_url = None if os.getenv("OPENAI_API_KEY") else os.getenv("ILMU_BASE_URL")
    if not api_key:
        print("ERROR: OPENAI_API_KEY (or ILMU_API_KEY) not set", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)

    raw_files = sorted(RAW_DIR.glob("*.txt"))
    if not raw_files:
        print(f"No .txt files in {RAW_DIR}. Run fetch_gov_docs.py first.")
        sys.exit(1)

    all_chunks: list[dict] = []
    for path in raw_files:
        chunks = chunk_file(path, args.domain)
        if chunks:
            print(f"  {path.name}: {len(chunks)} chunks (size={DOMAIN_CHUNK_SIZES.get(chunks[0]['domain'], DEFAULT_CHUNK_SIZE)})")
        all_chunks.extend(chunks)

    if not all_chunks:
        print("No chunks produced — check --domain filter or raw files.")
        sys.exit(1)

    print(f"\nTotal chunks to embed: {len(all_chunks)}")

    texts = [c["content"] for c in all_chunks]
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        print(f"  Embedding batch {i // EMBED_BATCH + 1}/{-(-len(texts) // EMBED_BATCH)} ({len(batch)} chunks)…")
        embeddings.extend(embed_batch(client, batch))

    for chunk, emb in zip(all_chunks, embeddings):
        chunk["embedding"] = emb

    with OUT_FILE.open("w", encoding="utf-8") as fh:
        for chunk in all_chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(all_chunks)} chunks → {OUT_FILE}")


if __name__ == "__main__":
    main()
