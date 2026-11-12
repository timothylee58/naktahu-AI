"""Prometheus metrics registry — HTTP RED metrics, agent metrics, circuit breakers.

This is additive, not a replacement for the existing observability layers:
- weave (app/core/weave_tracing.py) traces individual LangGraph node calls for
  debugging in the W&B UI — not a numeric time-series store.
- structlog (app/core/telemetry.py) gives searchable structured event logs.
- Sentry gives error tracking + sampled APM traces.

None of the above give a durable, queryable, alertable numeric metrics store.
This module is that: a Prometheus CollectorRegistry exposed via GET /metrics
(app/routers/metrics.py), scraped by an external Prometheus server.

Three metric families:
1. HTTP RED metrics — populated by middleware/prometheus_middleware.py on
   every request.
2. Agent-call metrics — dual-written from app/orchestration/metrics.py's
   record_agent_call(), which is the same funnel the existing in-memory JSON
   metrics collector uses. Both stay in sync from one call site.
3. Circuit-breaker state — NOT dual-written. Read lazily at scrape time via
   a custom Collector wrapping app.orchestration.circuit_breaker's existing
   get_all_breaker_metrics(), so circuit_breaker.py's hot path is untouched.

Multiple workers: start.sh runs uvicorn with --workers 2, and a Counter or
Histogram lives in ONE process's memory, so a plain /metrics scrape returned
whichever worker happened to answer: counters jumped up and down between
scrapes and rate() saw constant resets. Setting PROMETHEUS_MULTIPROC_DIR
(start.sh does) switches prometheus_client to multiprocess mode: every worker
writes into that directory and render_metrics() merges them. It must be set
before this module is imported, which is why start.sh exports it rather than
the app. With it unset (tests, a local single-process run) nothing changes.

Known limit: the circuit-breaker gauges (3) are read from the in-process
breaker, so they still describe only the worker that answered the scrape.
"""
from __future__ import annotations

import glob
import os
import re
from typing import Iterable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from prometheus_client.metrics_core import GaugeMetricFamily
from prometheus_client.registry import Collector

REGISTRY = CollectorRegistry()

# ── HTTP RED metrics (populated by PrometheusMiddleware) ───────────────────

http_requests_total = Counter(
    "naktahu_http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status_code"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "naktahu_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    registry=REGISTRY,
)

http_requests_in_progress = Gauge(
    "naktahu_http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method"],
    # Summed across live workers in multiprocess mode (ignored otherwise).
    multiprocess_mode="livesum",
    registry=REGISTRY,
)

# ── Agent-call metrics (dual-written from orchestration/metrics.py) ────────

agent_calls_total = Counter(
    "naktahu_agent_calls_total",
    "Total agent invocations",
    ["agent_name", "result"],  # result: success | failure | timeout
    registry=REGISTRY,
)

agent_call_duration_seconds = Histogram(
    "naktahu_agent_call_duration_seconds",
    "Agent invocation duration in seconds",
    ["agent_name"],
    registry=REGISTRY,
)

agent_confidence = Histogram(
    "naktahu_agent_confidence",
    "Agent result confidence score",
    ["agent_name"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=REGISTRY,
)

agent_tokens_total = Counter(
    "naktahu_agent_tokens_total",
    "Total tokens used by agent invocations",
    ["agent_name"],
    registry=REGISTRY,
)

agent_cache_hits_total = Counter(
    "naktahu_agent_cache_hits_total",
    "Total agent invocations served from cache",
    ["agent_name"],
    registry=REGISTRY,
)

agent_safety_flags_total = Counter(
    "naktahu_agent_safety_flags_total",
    "Total agent invocations flagged by safety checks",
    ["agent_name"],
    registry=REGISTRY,
)

# ── Business metrics: RAG pipeline provider/quality (populated by ───────────
#    synthesiser_node.py and analyst_node.py) ───────────────────────────────

rag_queries_total = Counter(
    "naktahu_rag_queries_total",
    "Total RAG queries by language and answering provider",
    # provider: "ilmu" (primary served it), "claude" (Anthropic fallback
    # served it), or "none" (both providers failed — the static apology
    # went out). Never "anthropic" — kept as "claude" to match the
    # CLAUDE_MODEL/FALLBACK_MODEL naming already used in llm_client.py.
    ["language", "provider"],
    registry=REGISTRY,
)

retrieval_score = Histogram(
    "naktahu_retrieval_score",
    # NOT a RAGAS-library score — this repo has no ragas dependency. This is
    # analyst_node's existing per-query confidence_score (chunk relevance +
    # gov-domain authority + recency-penalized staleness, averaged over the
    # top 3 cited chunks — see analyst_node.py's docstring), which is the
    # closest real per-query retrieval-quality signal this pipeline
    # computes. Named naktahu_retrieval_score, not naktahu_ragas_score, so
    # the metric doesn't claim a library this repo doesn't use.
    "Per-query retrieval confidence score (analyst_node's chunk-relevance confidence, 0-1)",
    buckets=(0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0),
    registry=REGISTRY,
)

provider_fallback_total = Counter(
    "naktahu_provider_fallback_total",
    "Times Claude was invoked as fallback because ILMU produced no usable output",
    registry=REGISTRY,
)

# ── Circuit breaker state (read lazily at scrape time) ─────────────────────

_BREAKER_STATE_VALUE = {"closed": 0, "open": 1, "half_open": 2}


class CircuitBreakerCollector(Collector):
    """Reads app.orchestration.circuit_breaker's existing metrics at scrape
    time — no dual-write, no change to circuit_breaker.py's hot path."""

    def collect(self) -> Iterable[GaugeMetricFamily]:
        from app.orchestration.circuit_breaker import get_all_breaker_metrics

        state = GaugeMetricFamily(
            "naktahu_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half_open)",
            labels=["provider"],
        )
        calls = GaugeMetricFamily(
            "naktahu_circuit_breaker_calls_total",
            "Total calls made through this circuit breaker",
            labels=["provider"],
        )
        failures = GaugeMetricFamily(
            "naktahu_circuit_breaker_failures_total",
            "Total failures recorded by this circuit breaker",
            labels=["provider"],
        )
        short_circuits = GaugeMetricFamily(
            "naktahu_circuit_breaker_short_circuits_total",
            "Total calls short-circuited (rejected without attempt) by this breaker",
            labels=["provider"],
        )
        recent_failures = GaugeMetricFamily(
            "naktahu_circuit_breaker_recent_failures",
            "Failures within the current rolling window",
            labels=["provider"],
        )

        for breaker in get_all_breaker_metrics():
            provider = breaker["provider"]
            state.add_metric([provider], _BREAKER_STATE_VALUE.get(breaker["state"], -1))
            calls.add_metric([provider], breaker["total_calls"])
            failures.add_metric([provider], breaker["total_failures"])
            short_circuits.add_metric([provider], breaker["total_short_circuits"])
            recent_failures.add_metric([provider], breaker["recent_failures"])

        yield state
        yield calls
        yield failures
        yield short_circuits
        yield recent_failures


REGISTRY.register(CircuitBreakerCollector())


_MULTIPROC_ENV = "PROMETHEUS_MULTIPROC_DIR"
_LIVE_GAUGE_FILE_PID = re.compile(r"gauge_live\w+_(\d+)\.db$")


def multiprocess_enabled() -> bool:
    return bool(os.environ.get(_MULTIPROC_ENV))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def prune_dead_gauge_files(directory: str) -> int:
    """Delete the live-gauge files of workers that no longer exist.

    uvicorn respawns a crashed worker under a new pid and never tells
    prometheus_client, so a dead worker's "requests in progress" would stay in
    the sum forever. Only the live-mode gauge files are touched; counters and
    histograms are cumulative and must keep a dead worker's totals.
    Returns how many files were removed.
    """
    removed = 0
    for path in glob.glob(os.path.join(directory, "gauge_live*_*.db")):
        match = _LIVE_GAUGE_FILE_PID.search(path)
        if match and not _pid_alive(int(match.group(1))):
            try:
                os.remove(path)
                removed += 1
            except FileNotFoundError:
                pass
    return removed


def render_metrics() -> bytes:
    """Render the metrics in Prometheus text-exposition format, merging every
    worker's samples when multiprocess mode is on (see the module docstring)."""
    directory = os.environ.get(_MULTIPROC_ENV)
    if not directory:
        return generate_latest(REGISTRY)
    prune_dead_gauge_files(directory)
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry, path=directory)
    registry.register(CircuitBreakerCollector())
    return generate_latest(registry)


__all__ = [
    "REGISTRY",
    "CONTENT_TYPE_LATEST",
    "render_metrics",
    "http_requests_total",
    "http_request_duration_seconds",
    "http_requests_in_progress",
    "agent_calls_total",
    "agent_call_duration_seconds",
    "agent_confidence",
    "agent_tokens_total",
    "agent_cache_hits_total",
    "agent_safety_flags_total",
    "rag_queries_total",
    "retrieval_score",
    "provider_fallback_total",
]
