"""router_node — fast intent/language/domain classifier using ILMU chat model."""
from __future__ import annotations

import json
import re

import structlog
import weave

from app.models.state import AgentState
from app.services.llm_client import ILMU_CHAT_MODEL, ilmu_client

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a query classifier for a Malaysian knowledge base. "
    "Return JSON with: language (bm, en, or zh for Mandarin Chinese), domain (one of: government, education, "
    "legal, finance, healthcare, epf, tax, business, immigration, culture), intent (string summary max 10 words). "
    "Detect language from the query text itself, not from any metadata."
)

_VALID_DOMAINS = {"government", "education", "legal", "finance", "healthcare", "epf", "tax", "business", "immigration", "culture"}
# Map common LLM outputs to stored domain values
_DOMAIN_ALIASES = {"health": "healthcare", "epf": "epf", "pension": "epf", "kwsp": "epf", "tax": "tax", "cukai": "tax"}
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# Unicode ranges that unambiguously identify script
_CJK_RE = re.compile(r'[一-鿿㐀-䶿豈-﫿]')


def _script_detect(query: str) -> str | None:
    """Return 'zh' if the query contains CJK characters, else None."""
    return "zh" if _CJK_RE.search(query) else None


@weave.op()
async def router_node(state: AgentState) -> dict:
    """Classify query intent, language, and domain."""
    query = state.get("query", "")

    # Deterministic script check before calling the LLM — CJK is unambiguous
    script_lang = _script_detect(query)

    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=128,
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        # Extract JSON even when the model wraps it in markdown fences
        m = _JSON_RE.search(raw)
        parsed = json.loads(m.group(0)) if m else {}
    except Exception as exc:
        log.warning("router_node_error", error=str(exc), query=query[:80])
        parsed = {}

    language = parsed.get("language", "en")
    if isinstance(language, str):
        language = language.strip().lower()
    if language not in {"bm", "en", "zh"}:
        language = "en"

    # Script detection overrides LLM when CJK characters are present —
    # ILMU may misclassify Mandarin queries as 'bm' since it's Malaysia-tuned
    if script_lang:
        language = script_lang

    domain = parsed.get("domain", "government")
    if isinstance(domain, str):
        domain = domain.strip().lower()
    domain = _DOMAIN_ALIASES.get(domain, domain)
    if domain not in _VALID_DOMAINS:
        domain = "government"

    log.info("router_classified", language=language, domain=domain)
    return {"language": language, "domain": domain}
