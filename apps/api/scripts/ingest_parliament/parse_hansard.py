"""
scripts/ingest_parliament/parse_hansard.py

Step 2 of the Hansard ingestion pipeline.
Parses downloaded Hansard PDFs into structured records.

What it does:
  1. Reads PDFs from data/raw/hansard/ (or a specific file).
  2. Extracts MP statements by detecting speaker transitions.
  3. Extracts division records (voting) when present.
  4. Outputs structured JSONL to data/processed/hansard_statements.jsonl
     and data/processed/hansard_votes.jsonl.

PDF library decision: pypdf, not pdfplumber. This repo already extracts PDF
text via pypdf (app/agents/tools.py::extract_pdf_text) for exam-paper
uploads; reusing the same well-understood, already-a-dependency library
avoids adding a new dependency for a marginal multi-column-layout benefit
that this pipeline does not lean on (it works over the concatenated text
stream, not per-column geometry).

RELIABILITY WARNING — read before trusting this output in any UI:
  Division-vote extraction (_extract_votes_from_division) is the LEAST
  reliable part of this pipeline. It relies on a loose regex to pull
  ALL-CAPS name-shaped tokens out of an AYES/NOES text block, which can
  easily capture non-name text (headers, procedural boilerplate, OCR noise
  from a scanned page). Every row produced by this pipeline is uploaded
  with mp_votes.source_verified = false (see upload_parliament.py) and
  MUST NOT be surfaced as authoritative, verified voting data in any UI
  without an explicit "unverified, scraped from Hansard" label. Manual
  verification is a human step, not something this pipeline claims to do.

Hansard structure (Dewan Rakyat):
  - Speaker transitions: "YB [Name] [Constituency]:"
  - Oral questions: "SOALAN MULUT" or "ORAL QUESTION"
  - Written questions: "SOALAN BERTULIS" or "WRITTEN QUESTION"
  - Division records: "AYES:", "NOES:", voting member lists
  - Bill readings: "BACAAN KALI YANG KEDUA" or "SECOND READING"

Run:
  python -m scripts.ingest_parliament.parse_hansard
  python -m scripts.ingest_parliament.parse_hansard --file data/raw/hansard/2025-07-07_DR.pdf
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import structlog
from pypdf import PdfReader

log = structlog.get_logger(__name__)

RAW_DIR = Path(__file__).parent / "data" / "raw" / "hansard"
PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

STATEMENTS_OUT = PROCESSED_DIR / "hansard_statements.jsonl"
VOTES_OUT = PROCESSED_DIR / "hansard_votes.jsonl"

# ── Regex patterns ──────────────────────────────────────────────────────────

# Speaker pattern: "YB NAMA PENUH [P.NNN - KAWASAN]:"
SPEAKER_RE = re.compile(
    r"(?:YB|YAB|YBhg|Datuk|Dato'|Tan Sri|Tun)[\s.]+([A-Z][A-Za-z\s'-]+?)"
    r"\s*\[([A-Z0-9.\s]+?)\]\s*:",
    re.UNICODE,
)

# Division (vote) record
DIVISION_RE = re.compile(
    r"AYES\s*[:\-]\s*(\d+)\s*\n(.*?)NOES\s*[:\-]\s*(\d+)\s*\n(.*?)(?=AYES|DIVISION|$)",
    re.DOTALL | re.IGNORECASE,
)

# Bill reading announcements
BILL_READING_RE = re.compile(
    r"(BACAAN KALI YANG (?:PERTAMA|KEDUA|KETIGA)|FIRST READING|SECOND READING|THIRD READING)"
    r"\s*[-–]\s*(.+)",
    re.IGNORECASE,
)

# Question types
ORAL_Q_RE = re.compile(r"SOALAN MULUT|ORAL QUESTION", re.IGNORECASE)
WRITTEN_Q_RE = re.compile(r"SOALAN BERTULIS|WRITTEN QUESTION", re.IGNORECASE)

# Constituency code extraction
CONST_CODE_RE = re.compile(r"\b(P\.?\d{3}|N\.\d+)\b")

# Tightened from the original `[A-Z][A-Z\s'-]{3,40}(?=\s*,|\s*\n)` (would
# happily capture any all-caps run — headers, "NOES", stray OCR noise).
# Requires: 2-5 space-separated ALL-CAPS word tokens (a name shape), each
# token >=2 chars, terminated by a comma or newline. Still a heuristic —
# hence source_verified=false downstream, never true.
_NAME_TOKEN = r"[A-Z][A-Z'-]{1,}"
DIVISION_NAME_RE = re.compile(
    rf"(?:{_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{1,4}})(?=\s*,|\s*\n)"
)

TOPIC_KEYWORDS = {
    "tax": ["cukai", "lhdn", "hasil", "tax", "GST", "SST", "percukaian"],
    "epf": ["KWSP", "EPF", "caruman", "pencen", "retirement"],
    "healthcare": ["kesihatan", "hospital", "doktor", "KKM", "health", "medical"],
    "education": ["pendidikan", "sekolah", "universiti", "PTPTN", "education"],
    "immigration": ["imigresen", "visa", "pasport", "warga asing", "immigration"],
    "business": ["perniagaan", "SSM", "syarikat", "business", "SME"],
    "housing": ["perumahan", "rumah", "PR1MA", "housing"],
    "transport": ["pengangkutan", "jalan raya", "LRT", "MRT", "transport"],
    "economy": ["ekonomi", "GDP", "inflasi", "economy", "budget", "bajet"],
    "security": ["keselamatan", "polis", "PDRM", "jenayah", "crime", "security"],
}


def _detect_topic(text: str) -> str:
    """Classify statement topic by keyword matching. Returns domain tag."""
    text_lower = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw.lower() in text_lower for kw in keywords):
            return topic
    return "general"


def _classify_statement_type(text: str, context: str) -> str:
    """Classify whether a statement is a question, debate, motion, etc."""
    if ORAL_Q_RE.search(context):
        return "oral_question"
    if WRITTEN_Q_RE.search(context):
        return "written_question"
    if re.search(r"usul|motion", text[:50], re.IGNORECASE):
        return "motion"
    if re.search(r"timbang tara|debate|debat", context, re.IGNORECASE):
        return "debate"
    if re.search(r"perintah tetap|standing order|point of order", text[:80], re.IGNORECASE):
        return "point_of_order"
    return "debate"


def _extract_votes_from_division(
    text: str,
    sitting_date: str,
    bill_number: str | None,
    source_url: str,
) -> list[dict]:
    """
    Parse division records from Hansard text. UNVERIFIED extraction — see
    module docstring's reliability warning. Returns list of vote dicts:
    {mp_name, vote, bill_number, sitting_date, source_url}.
    """
    votes = []
    for match in DIVISION_RE.finditer(text):
        ayes_text = match.group(2)
        noes_text = match.group(4)

        for name in DIVISION_NAME_RE.findall(ayes_text):
            votes.append({
                "mp_name": name.strip().title(),
                "vote": "for",
                "bill_number": bill_number,
                "sitting_date": sitting_date,
                "source_url": source_url,
            })

        for name in DIVISION_NAME_RE.findall(noes_text):
            votes.append({
                "mp_name": name.strip().title(),
                "vote": "against",
                "bill_number": bill_number,
                "sitting_date": sitting_date,
                "source_url": source_url,
            })

    return votes


def _extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_pdf(
    pdf_path: Path,
    sitting_date: str,
    parliament_no: int,
    session_no: int,
    source_url: str,
) -> tuple[list[dict], list[dict]]:
    """
    Parse a single Hansard PDF.

    Returns:
        statements: list of statement dicts (-> hansard_statements.jsonl)
        votes:      list of vote dicts     (-> hansard_votes.jsonl, UNVERIFIED)
    """
    statements: list[dict] = []
    sitting_id = f"DR.{sitting_date}"

    try:
        full_text = _extract_pdf_text(pdf_path)
    except Exception as exc:
        log.error("pdf_parse_failed", path=str(pdf_path), error=str(exc))
        return [], []

    log.info("pdf_parsed", path=pdf_path.name, chars=len(full_text))

    segments = re.split(SPEAKER_RE, full_text)

    current_bill_number: str | None = None
    for match in BILL_READING_RE.finditer(full_text):
        current_bill_number = match.group(2).strip()[:100]

    i = 1  # skip pre_text
    while i < len(segments) - 2:
        mp_name = segments[i].strip().title()
        const_hint = segments[i + 1].strip()
        content = segments[i + 2].strip() if i + 2 < len(segments) else ""
        i += 3

        if not content or len(content) < 30:
            continue

        content_trimmed = content[:1000]

        topic = _detect_topic(content_trimmed)
        stmt_type = _classify_statement_type(content_trimmed, full_text)
        word_count = len(content.split())
        const_code = CONST_CODE_RE.search(const_hint)

        statements.append({
            "sitting_id": sitting_id,
            "sitting_date": sitting_date,
            "parliament_no": parliament_no,
            "session_no": session_no,
            "mp_name": mp_name,
            "constituency_hint": const_hint,
            "constituency_code": const_code.group(0) if const_code else None,
            "statement_type": stmt_type,
            "topic_category": topic,
            "statement_bm": content_trimmed,
            "word_count": word_count,
            "bill_number": current_bill_number,
            "source_url": source_url,
            "hansard_page": None,  # enriched in a later pass
        })

    votes = _extract_votes_from_division(
        full_text, sitting_date, current_bill_number, source_url
    )

    log.info(
        "parse_complete",
        sitting_date=sitting_date,
        statements=len(statements),
        votes=len(votes),
        bill=current_bill_number,
    )
    return statements, votes


def process_manifest(manifest_path: Path | None = None) -> None:
    """Process all sittings listed in the manifest."""
    manifest = manifest_path or (RAW_DIR / "manifest.jsonl")
    if not manifest.exists():
        log.error("manifest_not_found", path=str(manifest))
        return

    all_statements: list[dict] = []
    all_votes: list[dict] = []

    with open(manifest) as f:
        for line in f:
            sitting = json.loads(line.strip())
            pdf_path = Path(sitting["local_path"])
            if not pdf_path.exists():
                log.warning("pdf_missing", path=str(pdf_path))
                continue

            stmts, votes = parse_pdf(
                pdf_path,
                sitting_date=sitting["sitting_date"],
                parliament_no=sitting.get("parliament_no", 15),
                session_no=sitting.get("session_no", 1),
                source_url=sitting.get("pdf_url", ""),
            )
            all_statements.extend(stmts)
            all_votes.extend(votes)

    with open(STATEMENTS_OUT, "w") as f:
        for s in all_statements:
            f.write(json.dumps(s, default=str) + "\n")

    with open(VOTES_OUT, "w") as f:
        for v in all_votes:
            f.write(json.dumps(v, default=str) + "\n")

    log.info(
        "processing_complete",
        total_statements=len(all_statements),
        total_votes=len(all_votes),
        out_statements=str(STATEMENTS_OUT),
        out_votes=str(VOTES_OUT),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=None, help="Process a single PDF")
    args = parser.parse_args()

    if args.file:
        from scripts.ingest_parliament.fetch_hansard import _parse_date_from_filename

        d = _parse_date_from_filename(args.file.name)
        if d:
            stmts, votes = parse_pdf(args.file, d.isoformat(), 15, 1, "")
            print(f"Extracted {len(stmts)} statements, {len(votes)} votes")
    else:
        process_manifest()
