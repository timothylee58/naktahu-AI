"""Judges that return P(claim is fully supported by the context).

Two implementations:

* LexicalOverlapJudge — a deterministic word-overlap baseline. It needs nothing,
  and any model judge must beat it in calibration or it is not worth running.
* JevDecideJudge — calls a self-hosted autotrust/JEV-27B-VL server's
  ``POST /v1/decide`` ("System 1": a calibrated probability for each option in
  one forward pass). The request and response shapes are taken from that model's
  card and have NOT been exercised against a live server from this repository's
  sandbox (no GPU, no route to Hugging Face): the first real run is the test.
  The model card lists English only, so no BM or ZH accuracy is assumed; that is
  what calibrate is for.

Sync on purpose: the eval-gate CI job installs only pytest and supabase.
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional, Protocol

_QUESTION = "Is the claim fully supported by the context above, with nothing added or changed?"
_MAX_CONTEXT_CHARS = 24_000


class JudgeError(RuntimeError):
    """The judge could not produce a probability for this claim."""


class Judge(Protocol):
    name: str

    def p_supported(self, *, context: str, claim: str) -> float: ...


_LATIN = re.compile(r"[a-z0-9]+")
_CJK_RUN = re.compile(r"[一-鿿]+")


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    tokens = {t for t in _LATIN.findall(lowered) if len(t) > 1 or t.isdigit()}
    for run in _CJK_RUN.findall(lowered):
        tokens.update(run[i : i + 2] for i in range(max(len(run) - 1, 1)))
    return tokens


class LexicalOverlapJudge:
    name = "lexical"

    def p_supported(self, *, context: str, claim: str) -> float:
        claim_tokens = _tokens(claim)
        if not claim_tokens:
            raise JudgeError("claim has no comparable tokens")
        return len(claim_tokens & _tokens(context)) / len(claim_tokens)


class JevDecideJudge:
    name = "jev"

    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        transport: Any = None,
    ) -> None:
        import httpx  # lazy: only needed when this judge is actually used

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport
        )

    @classmethod
    def from_env(cls) -> "JevDecideJudge":
        url = os.environ.get("JEV_URL", "").strip()
        if not url:
            raise JudgeError("JEV_URL is not set (the base URL of the JEV-27B-VL server)")
        return cls(url, api_key=os.environ.get("JEV_API_KEY") or None)

    def p_supported(self, *, context: str, claim: str) -> float:
        state = f"Context:\n{context[:_MAX_CONTEXT_CHARS]}\n\nClaim: {claim}"
        try:
            resp = self._client.post("/v1/decide", json={"kind": "noul", "state": state, "question": _QUESTION})
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:  # network, HTTP status, bad JSON
            raise JudgeError(f"decide request failed: {type(exc).__name__}") from exc
        try:
            options, probs = body["options"], body["probabilities"]
            p = float(probs[options.index("true")])
        except (KeyError, ValueError, IndexError, TypeError) as exc:
            raise JudgeError("decide response missing a 'true' probability") from exc
        if not 0.0 <= p <= 1.0:
            raise JudgeError(f"probability out of range: {p}")
        return p


def make_judge(name: str) -> Judge:
    if name == "lexical":
        return LexicalOverlapJudge()
    if name == "jev":
        return JevDecideJudge.from_env()
    raise JudgeError(f"unknown judge: {name}")
