"""Agent-level metrics collector.

Tracks per-agent performance metrics in-memory for the metrics endpoint.
Designed to be lightweight (no external dependencies like Prometheus) while
providing actionable visibility into agent health.

Metrics tracked per agent:
- Invocation count (total, success, failure, timeout)
- Latency histogram (p50, p75, p90, p95, p99)
- Confidence distribution (avg, min, max)
- Cache hit ratio
- Safety flag count
- Token usage

All metrics are since last reset (startup). The /metrics endpoint exposes
these as JSON for admin dashboards and alerting.
"""
from __future__ import annotations

import bisect
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger(__name__)


@dataclass
class AgentMetrics:
    """Accumulated metrics for a single agent."""

    agent_name: str
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    safety_flag_count: int = 0
    cache_hits: int = 0
    # Latency values in ms (sorted for percentile calculation)
    latencies: list[float] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)
    total_tokens: int = 0
    last_invoked_at: float = 0.0

    def record_invocation(
        self,
        *,
        success: bool,
        latency_ms: float,
        confidence: float = 0.0,
        timeout: bool = False,
        flagged: bool = False,
        cache_hit: bool = False,
        tokens_used: int = 0,
    ) -> None:
        """Record a single agent invocation."""
        self.total_calls += 1
        self.last_invoked_at = time.time()

        if timeout:
            self.timeout_count += 1
        elif success:
            self.success_count += 1
        else:
            self.failure_count += 1

        if flagged:
            self.safety_flag_count += 1
        if cache_hit:
            self.cache_hits += 1

        # Keep latencies sorted for percentile calculation (cap at 10000 entries)
        bisect.insort(self.latencies, latency_ms)
        if len(self.latencies) > 10000:
            self.latencies = self.latencies[-5000:]

        if confidence > 0:
            self.confidences.append(confidence)
            if len(self.confidences) > 10000:
                self.confidences = self.confidences[-5000:]

        self.total_tokens += tokens_used

    def _percentile(self, values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        idx = int(len(values) * pct / 100)
        idx = min(idx, len(values) - 1)
        return round(values[idx], 2)

    def to_dict(self) -> dict[str, Any]:
        """Export metrics as a JSON-serializable dict."""
        return {
            "agent_name": self.agent_name,
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "safety_flag_count": self.safety_flag_count,
            "cache_hits": self.cache_hits,
            "cache_hit_ratio": round(self.cache_hits / max(self.total_calls, 1), 4),
            "success_rate": round(self.success_count / max(self.total_calls, 1), 4),
            "latency": {
                "p50": self._percentile(self.latencies, 50),
                "p75": self._percentile(self.latencies, 75),
                "p90": self._percentile(self.latencies, 90),
                "p95": self._percentile(self.latencies, 95),
                "p99": self._percentile(self.latencies, 99),
                "count": len(self.latencies),
            },
            "confidence": {
                "avg": round(sum(self.confidences) / max(len(self.confidences), 1), 4),
                "min": round(min(self.confidences), 4) if self.confidences else 0.0,
                "max": round(max(self.confidences), 4) if self.confidences else 0.0,
            },
            "total_tokens": self.total_tokens,
            "last_invoked_at": self.last_invoked_at,
        }


# ── Global metrics registry ────────────────────────────────────────────────────

_metrics: dict[str, AgentMetrics] = defaultdict(lambda: AgentMetrics(agent_name=""))


def record_agent_call(
    agent_name: str,
    *,
    success: bool,
    latency_ms: float,
    confidence: float = 0.0,
    timeout: bool = False,
    flagged: bool = False,
    cache_hit: bool = False,
    tokens_used: int = 0,
) -> None:
    """Record metrics for a single agent invocation.

    Called by the executor after each agent completes (or fails).
    """
    if agent_name not in _metrics:
        _metrics[agent_name] = AgentMetrics(agent_name=agent_name)

    _metrics[agent_name].record_invocation(
        success=success,
        latency_ms=latency_ms,
        confidence=confidence,
        timeout=timeout,
        flagged=flagged,
        cache_hit=cache_hit,
        tokens_used=tokens_used,
    )


def get_all_metrics() -> list[dict[str, Any]]:
    """Return metrics for all agents (for the /metrics endpoint)."""
    return [m.to_dict() for m in _metrics.values() if m.total_calls > 0]


def get_agent_metrics(agent_name: str) -> dict[str, Any] | None:
    """Return metrics for a specific agent."""
    m = _metrics.get(agent_name)
    return m.to_dict() if m and m.total_calls > 0 else None


def get_summary() -> dict[str, Any]:
    """High-level summary across all agents."""
    total_calls = sum(m.total_calls for m in _metrics.values())
    total_success = sum(m.success_count for m in _metrics.values())
    total_failures = sum(m.failure_count for m in _metrics.values())
    total_timeouts = sum(m.timeout_count for m in _metrics.values())
    total_flags = sum(m.safety_flag_count for m in _metrics.values())

    return {
        "total_calls": total_calls,
        "total_success": total_success,
        "total_failures": total_failures,
        "total_timeouts": total_timeouts,
        "total_safety_flags": total_flags,
        "success_rate": round(total_success / max(total_calls, 1), 4),
        "agent_count": len([m for m in _metrics.values() if m.total_calls > 0]),
    }


def reset_metrics() -> None:
    """Reset all metrics (for testing or admin use)."""
    _metrics.clear()
