"""Knowledge context loader for PatuhiKu agents.

Design intent (read this before changing the implementation):

Each domain (tax / payroll / corporate) has ~10-20 facts that change a few times
a year. At that volume and update frequency, a vector DB adds retrieval latency
and a new failure surface (chunking quality, embedding drift, wrong-snippet
retrieval) for marginal benefit over just handing the agent the whole file.

The PUBLIC INTERFACE below — get_context(domain) -> AgentContext — is the only
thing agent nodes are allowed to depend on. Today it parses static markdown.
If a domain's knowledge base grows past a few hundred facts, or starts
changing weekly instead of quarterly, swap _load_static() for a pgvector
similarity search WITHOUT touching any agent code, because the return shape
(AgentContext) stays identical either way.

That's the whole contract: agents ask "what do you know about domain X,
optionally relevant to query Y" and get back dated, sourced text. How that
answer is produced is this module's problem, not the agent's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


@dataclass
class AgentContext:
    domain: str
    as_of: date
    sources: list[str]
    review_cycle: str
    content: str  # full markdown body, facts + reasoning notes, ready to drop into a prompt
    facts: list[str] = field(default_factory=list)  # flattened bullet facts, for quick scanning/logging

    def is_stale(self, max_age_days: int = 120) -> bool:
        """Quarterly review_cycle ~ 90 days; flag at 120 so a missed review trips a warning,
        not a silent failure. Agents/tests can check this instead of eyeballing dates."""
        return (date.today() - self.as_of).days > max_age_days

    def as_prompt_block(self) -> str:
        """What actually gets injected into the agent's system/context message."""
        staleness_note = (
            f"\n[NOTE: this knowledge is {(date.today() - self.as_of).days} days old "
            f"— review cycle is '{self.review_cycle}', consider re-verifying volatile figures.]"
            if self.is_stale()
            else ""
        )
        return (
            f"# Knowledge base: {self.domain} (as of {self.as_of.isoformat()})\n"
            f"Sources: {', '.join(self.sources)}\n"
            f"{self.content}"
            f"{staleness_note}"
        )


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Minimal frontmatter parser — avoids pulling in a yaml dependency for ~5 known keys."""
    if not raw.startswith("---"):
        return {}, raw

    _, fm_block, body = raw.split("---", 2)
    meta: dict = {}
    for line in fm_block.strip().splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        value = value.split("  #", 1)[0].strip()  # strip trailing inline comments, e.g. "quarterly  # why"
        if key == "sources":
            continue  # sources is a YAML list below this key; handled separately
        meta[key] = value

    # sources: appears as a bare key followed by "  - url" lines
    sources = re.findall(r"^\s*-\s*(\S+)$", fm_block, flags=re.MULTILINE)
    meta["sources"] = sources

    return meta, body.strip()


def _extract_facts(body: str) -> list[str]:
    """Pulls top-level bullet points for quick scanning/logging — the full `content`
    (with headers + reasoning notes) is still what gets sent to the model. Bullets
    that wrap onto a continuation line (no leading '-') are joined into one fact."""
    facts: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            facts.append(stripped[2:].strip())
        elif stripped and facts and not stripped.startswith(("#", "-")):
            facts[-1] = f"{facts[-1]} {stripped}"
    return facts


def _load_static(domain: str) -> AgentContext:
    path = KNOWLEDGE_DIR / f"{domain}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"No knowledge file for domain '{domain}' at {path}. "
            f"Available domains: {[p.stem for p in KNOWLEDGE_DIR.glob('*.md')]}"
        )

    raw = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)

    return AgentContext(
        domain=meta.get("domain", domain),
        as_of=date.fromisoformat(meta["as_of"]),
        sources=meta.get("sources", []),
        review_cycle=meta.get("review_cycle", "unknown"),
        content=body,
        facts=_extract_facts(body),
    )


@lru_cache(maxsize=8)
def get_context(domain: str, query: str | None = None) -> AgentContext:
    """
    Public interface every agent node calls.

    `query` is accepted but unused today — it's the seam where a future RAG swap
    would do similarity search instead of returning the whole file. Keeping it
    in the signature now means callers don't need to change when that swap happens.

    Example (future v2, same call site in agent code):
        def _load_static(domain, query):
            return pgvector_similarity_search(domain, query, top_k=5)
    """
    return _load_static(domain)


def list_domains() -> list[str]:
    return sorted(p.stem for p in KNOWLEDGE_DIR.glob("*.md"))
