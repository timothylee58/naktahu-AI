#!/usr/bin/env python3
"""Show what retrieval returns for specific answer-key questions, under each embedding profile.

The live tax eval says a question was answered wrongly; this says whether the chunk that
holds the right answer was retrieved at all, and if not, why. For each case and profile it
runs the SAME search the pipeline runs (rag_node -> vector_store.hybrid_search: the profile's
RPC, the Malay-affix keyword query, match_count) and reports:

  * the top results with no domain filter (title, similarity, whether each carries the answer);
  * the 1-based rank of the first chunk that carries the answer, unfiltered;
  * the same rank under each domain filter the router can emit. The pipeline hard-filters on the
    router's domain, so an answer chunk stored under another domain is invisible to it; this
    sweep is what shows that.

"Carries the answer" = the chunk text contains, for every must_contain group of the case in
evals/tax_accuracy.jsonl, at least one of the group's phrases (case-insensitive substring).
Some cases check a computed figure that no chunk contains (stamp-duty-600k expects the
arithmetic result), so ANSWER_SOURCE maps them to the case whose groups describe the source
facts. This is a coarse text match, not a judgement: read the titles it prints.

Read-only: it embeds queries and calls search RPCs, and writes nothing.

    python -m scripts.retrieval_probe                       # default cases, both profiles
    python -m scripts.retrieval_probe --cases spouse-relief --profiles ilmu_bge_m3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

# Same list as router_node._VALID_DOMAINS (the domains the pipeline may filter on).
ROUTER_DOMAINS = (
    "government", "education", "legal", "finance", "healthcare", "epf", "tax",
    "business", "immigration", "culture", "parliament", "property", "welfare",
)
DEFAULT_CASES = (
    "spouse-relief", "non-resident-individual-rate", "rpgt-citizen-3-years", "stamp-duty-600k",
)
# Cases whose expected figure is computed, not stated: judge the chunks against the source facts.
ANSWER_SOURCE = {"stamp-duty-600k": "stamp-duty-property-rates"}
MATCH_COUNT = 10
KEY_FILE = _API_ROOT / "evals" / "tax_accuracy.jsonl"


def load_cases(path: Path = KEY_FILE) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            case = json.loads(line)
            cases[case["id"]] = case
    return cases


def carries_answer(text: str, groups: list[list[str]]) -> bool:
    """True when, for every group, at least one phrase appears in the text."""
    lowered = (text or "").lower()
    return bool(groups) and all(any(p.lower() in lowered for p in group) for group in groups)


def first_rank(rows: list[dict[str, Any]], groups: list[list[str]]) -> Optional[int]:
    """1-based rank of the first row that carries the answer, or None."""
    for index, row in enumerate(rows, start=1):
        if carries_answer(str(row.get("content") or ""), groups):
            return index
    return None


def search_params(query: str, embedding: list[float], domain: Optional[str]) -> dict[str, Any]:
    """The parameters vector_store.hybrid_search sends for the same inputs."""
    from app.services.malay_morph import build_keyword_tsquery

    params: dict[str, Any] = {"query_text": query, "query_embedding": embedding, "match_count": MATCH_COUNT}
    if domain is not None:
        params["domain_filter"] = domain
    keyword_query = build_keyword_tsquery(query)
    if keyword_query is not None:
        params["keyword_query"] = keyword_query
    return params


def _search(supabase: Any, rpc: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return supabase.rpc(rpc, params).execute().data or []


def _short(text: str, width: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 1] + "…"


async def probe_case(supabase: Any, case: dict[str, Any], groups: list[list[str]], profile: Any) -> list[str]:
    from app.agents.rag_node import embed_with_profile

    query = case["query"]
    embedding = await embed_with_profile(query, profile)
    lines = [f"  [{profile.name}]"]
    unfiltered = _search(supabase, profile.chunks_rpc, search_params(query, embedding, None))
    rank = first_rank(unfiltered, groups)
    lines.append(f"    unfiltered: answer chunk at rank {rank if rank else f'- (not in top {MATCH_COUNT})'}")
    for index, row in enumerate(unfiltered[:5], start=1):
        mark = "ANSWER" if carries_answer(str(row.get("content") or ""), groups) else "      "
        lines.append(
            f"      {index}. {mark} sim={float(row.get('similarity') or 0):.3f} "
            f"{_short(str(row.get('source_title') or ''), 60)}  [{_short(str(row.get('source_url') or ''), 50)}]"
        )
    by_domain: list[str] = []
    for domain in ROUTER_DOMAINS:
        try:
            rows = _search(supabase, profile.chunks_rpc, search_params(query, embedding, domain))
        except Exception as exc:
            by_domain.append(f"{domain}=ERROR({type(exc).__name__})")
            continue
        r = first_rank(rows, groups)
        by_domain.append(f"{domain}={'#' + str(r) if r else ('none' if rows else 'empty')}")
    lines.append("    under each router domain filter (#rank | none = results but no answer | empty = no results):")
    lines.append("      " + "  ".join(by_domain))
    return lines


async def main_async(args: argparse.Namespace) -> int:
    from supabase import create_client

    from app.services.embedding_profiles import PROFILES
    from core.config import settings

    cases = load_cases()
    unknown = [c for c in args.cases if c not in cases]
    if unknown:
        print(f"Unknown case id(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    for case_id in args.cases:
        case = cases[case_id]
        source_id = ANSWER_SOURCE.get(case_id, case_id)
        groups = cases[source_id]["must_contain_groups"]
        note = f" (answer facts taken from {source_id})" if source_id != case_id else ""
        print(f"\n=== {case_id}: {case['query']}\n    answer = {groups}{note}")
        for name in args.profiles:
            try:
                for line in await probe_case(supabase, case, groups, PROFILES[name]):
                    print(line)
            except Exception as exc:
                print(f"  [{name}] ERROR {type(exc).__name__}: {str(exc)[:160]}")
    return 0


def main() -> int:
    from_profiles = ("openai", "ilmu_bge_m3")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", nargs="+", default=list(DEFAULT_CASES), help="answer-key case ids")
    parser.add_argument("--profiles", nargs="+", default=list(from_profiles), choices=from_profiles)
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
