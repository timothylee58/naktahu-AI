"""Chunk raw text files and generate OpenAI embeddings.

Reads  : scripts/ingest/data/raw/{domain}_{slug}.txt
Outputs: scripts/ingest/data/processed/chunks.jsonl

Each JSONL line contains:
  id, content, language, domain, source_title, source_url, ministry, embedding

Run:
    python scripts/ingest/chunk_and_embed.py
"""
from __future__ import annotations

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

CHUNK_SIZE = 512        # tokens ≈ chars / 4; we use chars directly
CHUNK_OVERLAP = 64
CHARS_PER_TOKEN = 4     # rough approximation

EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_BATCH = 50        # OpenAI allows up to 2048 per request


HEADER_RE = re.compile(
    r"SOURCE_TITLE:\s*(.+)\n"
    r"SOURCE_URL:\s*(.+)\n"
    r"MINISTRY:\s*(.+)\n"
    r"DOMAIN:\s*(.+)\n"
    r"---\n",
)


def parse_header(raw: str) -> tuple[dict[str, str], str]:
    """Split the metadata header from body text."""
    m = HEADER_RE.match(raw)
    if not m:
        raise ValueError("Missing metadata header in file")
    meta = {
        "source_title": m.group(1).strip(),
        "source_url": m.group(2).strip(),
        "ministry": m.group(3).strip(),
        "domain": m.group(4).strip(),
    }
    body = raw[m.end():]
    return meta, body


def detect_language(text: str) -> str:
    """Return 'bm' for Malay or 'en' for English using pycld2."""
    try:
        _, _, best = pycld2.detect(text[:2000])
        lang_code = best[0][1]  # ISO 639-1 code
        return "bm" if lang_code in ("ms", "id") else "en"
    except Exception:
        return "en"


def embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API for a batch of texts."""
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in resp.data]


def chunk_file(path: Path, splitter: RecursiveCharacterTextSplitter) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    try:
        meta, body = parse_header(raw)
    except ValueError:
        # Fallback: infer domain from filename ({domain}_{slug}.txt)
        parts = path.stem.split("_", 1)
        meta = {
            "source_title": path.stem.replace("_", " ").title(),
            "source_url": "",
            "ministry": "Unknown",
            "domain": parts[0] if parts else "government",
        }
        body = raw

    chunks = splitter.split_text(body)
    records = []
    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 80:          # skip tiny fragments
            continue
        records.append({
            "id": str(uuid.uuid4()),
            "content": chunk,
            "language": detect_language(chunk),
            "domain": meta["domain"],
            "source_title": meta["source_title"],
            "source_url": meta["source_url"],
            "ministry": meta["ministry"],
            "embedding": None,       # filled in after batched embedding
        })
    return records


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE * CHARS_PER_TOKEN,
        chunk_overlap=CHUNK_OVERLAP * CHARS_PER_TOKEN,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_files = sorted(RAW_DIR.glob("*.txt"))
    if not raw_files:
        print(f"No .txt files found in {RAW_DIR}. Run fetch_gov_docs.py first.")
        sys.exit(1)

    all_chunks: list[dict] = []
    for path in raw_files:
        chunks = chunk_file(path, splitter)
        print(f"  {path.name}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"\nTotal chunks to embed: {len(all_chunks)}")

    # Batch embed
    texts = [c["content"] for c in all_chunks]
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        print(f"  Embedding batch {i // EMBED_BATCH + 1} ({len(batch)} chunks)…")
        embeddings.extend(embed_batch(client, batch))

    for chunk, emb in zip(all_chunks, embeddings):
        chunk["embedding"] = emb

    with OUT_FILE.open("w", encoding="utf-8") as fh:
        for chunk in all_chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(all_chunks)} chunks → {OUT_FILE}")


if __name__ == "__main__":
    main()
