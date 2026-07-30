"""guard_node — topic scope check after routing.

Rejects queries that are clearly outside the Malaysian public-service domain
before RAG retrieval is attempted. Returns a refusal message written via
get_stream_writer() so the SSE endpoint receives it like any other token stream.

Two layers of defense:
1. A harmful-intent keyword list (hard, fast, free). Always active.
2. A best-effort LLM intent classifier (ILMU chat model) for queries that pass
   the keyword check, to catch novel jailbreak/harmful-intent phrasings that
   don't contain any of the listed keywords. This second pass is soft: any
   failure (timeout, API error, malformed JSON) fails OPEN — the query
   proceeds to rag_node rather than being blocked, so an ILMU outage never
   becomes an availability incident or a source of false positives.

   DISABLED BY DEFAULT (settings.guard_llm_check_enabled) as of the
   incident where it wrongly flagged three unrelated benign civic queries
   as harmful — lost ID document, contacting an MP, registering a company
   — despite two rounds of system-prompt tuning (_GUARD_LLM_SYSTEM_PROMPT
   below still documents that tuning for whenever this is re-enabled).
   Prompt-only mitigation did not hold across topics, so layer 2 is opt-in
   via GUARD_LLM_CHECK_ENABLED=true until its real-world false-positive
   rate is understood. Layer 1 is unaffected and still blocks every
   listed keyword regardless of this setting.

The query's ``domain`` label is deliberately NOT used as a block reason. The
router forces every real classification into a valid domain, so a
domain-whitelist check could only ever fire on the app's ``"general"`` default
sentinel (an unclassified — but perfectly in-scope — query), refusing legitimate
questions like "What should I do if I lose my MyKad?". Off-topic queries instead
fall through to rag_node and surface a low-confidence clarification, never a hard
scope refusal.
"""
from __future__ import annotations

import re

import structlog
import weave
from langgraph.config import get_stream_writer

from app.models.state import AgentState
from core.config import settings

log = structlog.get_logger(__name__)

# Intents that signal out-of-scope requests regardless of domain label
_BLOCKED_INTENT_KEYWORDS = [
    "hack", "crack", "exploit", "malware", "phishing", "keylogger",
    "ddos", "ransomware", "bypass security", "steal credentials",
    "how to cheat", "how to forge", "counterfeit", "scam people",
    "generate fake", "create fake id", "bomb", "weapon", "drug synthesis",
    "make drugs", "synthesize drugs",
]

# Victim/reporting-context phrasing that shares vocabulary with the blocked
# keywords above but describes someone seeking help after being targeted,
# not someone requesting how-to instructions. If present alongside a keyword
# hit, the query is treated as legitimate rather than blocked. Also applied
# as a safety net over the LLM classifier's verdict (see guard_node()) — a
# civic-service query like "lost my MyKad" shares vocabulary (identity
# document, replacement, loss) with fraud/identity-theft phrasing and has
# been observed to trip the LLM classifier as a false positive with no
# code-level check to catch it, unlike the keyword layer below.
_BENIGN_CONTEXT_RE = re.compile(
    r"(victim of|hacked my|was hacked|got hacked|"
    r"report(?:ing)? (?:a |an )?(?:scam|hack|hacking|ransomware|phishing|fraud)|"
    r"protect myself from|recover from|"
    r"complain(?:t)? (?:process|to)|steps? (?:to take|should i take)|"
    r"file a (?:police )?report|"
    r"report (?:it )?to (?:the )?(?:police|pdrm|bank negara|nacsa|cybersecurity malaysia)|"
    r"lo(?:st|se|sing).{0,25}(?:mykad|ic|identity card|id card|passport)|"
    r"(?:mykad|kad pengenalan|kad|pasport).{0,15}hilang|"
    r"hilang.{0,15}(?:mykad|kad pengenalan|kad|pasport)|"
    r"kehilangan.{0,25}(?:mykad|kad pengenalan|pasport)|"
    r"replace.{0,25}(?:mykad|identity card|id card|passport)|"
    r"ganti(?:kan)?.{0,25}(?:mykad|kad pengenalan|pasport)|"
    r"(?:member of parliament|\bmp\b|adun|councillor|elected representative).{0,40}"
    r"(?:contact|reach|hubungi|email|phone)|"
    r"(?:contact|reach|hubungi|email|phone).{0,40}"
    r"(?:member of parliament|\bmp\b|adun|councillor|elected representative)|"
    r"who is (?:the |my )?(?:mp|member of parliament|adun|councillor)|"
    r"(?:ahli parlimen|wakil rakyat|wakil parlimen).{0,40}"
    r"(?:kawasan|hubungi|hubung)|"
    r"(?:kawasan|hubungi).{0,40}(?:ahli parlimen|wakil rakyat|wakil parlimen)|"
    r"siapakah ahli parlimen|"
    r"voting record|parliamentary statement|"
    r"licen[cs]e to (?:legally )?(?:own|possess|carry)|"
    r"apply for a (?:firearm|gun|weapon) licen[cs]e|"
    r"legal(?:ly)? (?:own|possess) a weapon|"
    r"sport shooting|"
    r"legal penalty|legal punishment|under the .* act|"
    # Chinese-script equivalents. The app is trilingual (bm/en/zh — see
    # CLAUDE.md and test_guard_node.py's _ALL_SUGGESTED_QUERIES), and
    # router_node's classifier prompt does not force the `intent` summary
    # to be in English for a zh query, so this override must not depend on
    # a Latin substring being present anywhere in the combined
    # intent+query string — see the audit finding that flagged this gap.
    r"(?:身份证|护照|证件).{0,15}(?:遗失|丢失|不见了|弄丢)|"
    r"(?:遗失|丢失|弄丢).{0,15}(?:身份证|护照|证件)|"
    r"(?:议员|国会议员|州议员).{0,20}(?:联系|联络|联络方式)|"
    r"(?:联系|联络).{0,20}(?:议员|国会议员|州议员)|"
    r"选区议员是谁|我的议员)",
    re.IGNORECASE,
)


_GUARD_LLM_SYSTEM_PROMPT = (
    "You are a safety classifier for a Malaysian public-service Q&A system. "
    "Given a user query, decide whether it has harmful, malicious, or clearly "
    "out-of-scope intent (e.g. jailbreak attempts, requests to bypass security "
    "or verification systems, fraud, or other adversarial phrasing), even if it "
    "does not contain obvious keywords. "
    "This system exists to help ordinary citizens navigate Malaysian public "
    "services. The following are ALWAYS benign and must be classified "
    "harmful=false, even though they superficially share vocabulary with "
    "sensitive categories: replacing or reporting a lost/stolen identity "
    "document (MyKad, passport); finding and contacting one's own elected "
    "representative (MP, ADUN, councillor) through official government "
    "channels — this is a citizen's basic civic right, not a privacy or "
    "doxxing concern, since MPs' official contact details are public "
    "government information; looking up a public official's voting record "
    "or parliamentary statements; applying for a legally-regulated licence "
    "(firearm, weapon) through the proper government process; and any query "
    "that merely describes being a victim of a scam, hack, or fraud while "
    "seeking help or reporting it. Only classify harmful=true for genuine "
    "adversarial intent — requests to bypass, forge, exploit, or obtain "
    "unauthorized access — not for ordinary civic-service questions that "
    "happen to mention a sensitive-sounding noun. "
    'Return JSON only: {"harmful": true or false, "reason": "short reason"}.'
)


def _is_blocked_intent(intent: str, query: str = "") -> bool:
    lower = intent.lower()
    if not any(kw in lower for kw in _BLOCKED_INTENT_KEYWORDS):
        return False
    # A blocked keyword hit in the (short, ~10-word) intent summary can still
    # be a false positive if the full query establishes legitimate context
    # that the summary dropped — check both before blocking.
    combined = f"{lower} {query.lower()}"
    if _BENIGN_CONTEXT_RE.search(combined):
        return False
    return True


async def _is_harmful_by_llm(query: str) -> bool:
    """Best-effort second-pass intent classifier via the ILMU chat model.

    Fails OPEN on any error — this is a soft improvement layered on top of the
    hard keyword-based guard, never a new availability risk or source of
    false positives.
    """
    if not settings.guard_llm_check_enabled:
        return False

    # Imported lazily so tests can patch app.agents.guard_node.ilmu_client
    # without requiring ILMU credentials at import time.
    from app.services.llm_client import ILMU_CHAT_MODEL, extract_json_object, ilmu_client

    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _GUARD_LLM_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=64,
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        # extract_json_object handles trailing commentary after the JSON —
        # a naive greedy regex here previously matched through to the LAST
        # '}' anywhere in the completion, corrupting the parse the moment
        # the model appended any text containing a brace.
        parsed = extract_json_object(raw)
        return bool(parsed.get("harmful", False))
    except Exception as exc:
        log.warning("guard_llm_check_failed_open", error=str(exc), query_len=len(query))
        return False


def _refusal_message(lang: str) -> str:
    if lang == "bm":
        return (
            "Maaf, NakTahu AI hanya boleh menjawab soalan berkaitan perkhidmatan awam, "
            "undang-undang, pendidikan, kewangan, kesihatan, dan hal ehwal rakyat Malaysia. "
            "Soalan anda berada di luar skop sistem ini."
        )
    if lang == "zh":
        return (
            "抱歉，NakTahu AI 只能回答与马来西亚公共服务、法律、教育、金融、"
            "医疗保健及公民事务相关的问题。您的问题超出本系统的范围。"
        )
    return (
        "Sorry, NakTahu AI is designed to answer questions about Malaysian public services, "
        "law, education, finance, healthcare, and civic affairs. "
        "Your query is outside the scope of this system."
    )


@weave.op()
async def guard_node(state: AgentState) -> dict:
    """Block off-topic or harmful queries; let valid ones pass through unchanged."""
    domain: str = state.get("domain", "government")
    intent: str = state.get("intent", "")
    lang: str = state.get("language", "en")
    query: str = state.get("query", "")

    # Only harmful intent blocks a query. The domain label is intentionally not
    # a block reason — see module docstring (the "general" sentinel is in-scope).
    blocked = _is_blocked_intent(intent, query)

    # Second-pass LLM check only runs if the keyword check didn't already block
    # the query — the hard keyword pass always short-circuits.
    if not blocked and query:
        blocked = await _is_harmful_by_llm(query)
        # The LLM classifier gets the same benign-context safety net as the
        # keyword layer above — it is a soft, best-effort pass and has been
        # observed to false-positive on ordinary civic-service queries (e.g.
        # "lost my MyKad") that share vocabulary with fraud/identity-theft
        # phrasing. Without this override there was no way to recover from a
        # bad LLM verdict, unlike the keyword path.
        if blocked and _BENIGN_CONTEXT_RE.search(f"{intent.lower()} {query.lower()}"):
            blocked = False

    if blocked:
        log.warning("guard_node_blocked", domain=domain, intent=intent)
        write = get_stream_writer()
        msg = _refusal_message(lang)
        # Emit refusal as a single token chunk so the SSE layer handles it uniformly
        write(msg)
        return {"streaming_token_buffer": msg, "needs_clarification": False, "error": "blocked"}

    return {}
