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
"""
from __future__ import annotations

from typing import Iterable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
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


def render_metrics() -> bytes:
    """Render the full registry in Prometheus text-exposition format."""
    return generate_latest(REGISTRY)


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
]
