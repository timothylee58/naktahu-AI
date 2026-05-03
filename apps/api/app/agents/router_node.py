"""router_node — fast intent/language/domain classifier using ILMU chat model."""
from __future__ import annotations

import json
import re

import structlog

from app.models.state import AgentState
from app.services.llm_client import ILMU_CHAT_MODEL, ilmu_client

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a query classifier for a Malaysian knowledge base. "
    "Return JSON with: language (bm or en), domain (one of: government, education, "
    "legal, finance, health, culture), intent (string summary max 10 words). "
    "Detect language from the query text itself, not from any metadata."
)

_VALID_DOMAINS = {"government", "education", "legal", "finance", "health", "culture"}
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


async def router_node(state: AgentState) -> dict:
    """Classify query intent, language, and domain."""
    query = state.get("query", "")
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
    if language not in {"bm", "en"}:
        language = "en"

    domain = parsed.get("domain", "government")
    if isinstance(domain, str):
        domain = domain.strip().lower()
    if domain not in _VALID_DOMAINS:
        domain = "government"

    log.info("router_classified", language=language, domain=domain)
    return {"language": language, "domain": domain}
