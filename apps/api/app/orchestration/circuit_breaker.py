"""CircuitBreaker — per-provider resilience wrapper for LLM calls.

Implements the circuit breaker pattern to prevent cascading failures when
an LLM provider (ILMU, Anthropic, OpenAI embeddings) is degraded or down.

States:
- CLOSED: normal operation, requests pass through
- OPEN: provider is considered down, requests fail fast (or route to fallback)
- HALF_OPEN: after recovery_timeout, allows a single probe request through

Transitions:
- CLOSED → OPEN: when failure_count >= failure_threshold within the window
- OPEN → HALF_OPEN: after recovery_timeout seconds elapse
- HALF_OPEN → CLOSED: probe request succeeds
- HALF_OPEN → OPEN: probe request fails (resets recovery timer)

Usage:
    breaker = CircuitBreaker("ilmu", failure_threshold=5, recovery_timeout=60)
    try:
        result = await breaker.call(ilmu_client.chat.completions.create, ...)
    except CircuitOpenError:
        # Use fallback provider
        result = await anthropic_fallback(...)
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar

import structlog

log = structlog.get_logger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    closed = "closed"
    open = "open"
    half_open = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""

    def __init__(self, provider: str, time_until_probe: float) -> None:
        self.provider = provider
        self.time_until_probe = time_until_probe
        super().__init__(
            f"Circuit breaker OPEN for '{provider}'. "
            f"Next probe in {time_until_probe:.1f}s."
        )


class CircuitBreaker:
    """Per-provider circuit breaker with configurable thresholds.

    Thread-safe for asyncio (single event loop). Not thread-safe across
    multiple OS threads, but FastAPI runs on a single event loop so this
    is fine for our use case.
    """

    def __init__(
        self,
        provider: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        failure_window: float = 120.0,
        success_threshold: int = 2,
    ) -> None:
        """
        Args:
            provider: Human-readable provider name (for logging/metrics).
            failure_threshold: Consecutive failures before opening the circuit.
            recovery_timeout: Seconds to wait in OPEN before allowing a probe.
            failure_window: Time window (seconds) in which failures are counted.
                Failures older than this are discarded.
            success_threshold: Consecutive successes in HALF_OPEN before closing.
        """
        self.provider = provider
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_window = failure_window
        self.success_threshold = success_threshold

        self._state = CircuitState.closed
        self._failure_timestamps: deque[float] = deque()
        self._last_failure_time: float = 0.0
        self._half_open_successes: int = 0
        self._lock = asyncio.Lock()

        # Metrics
        self._total_calls: int = 0
        self._total_failures: int = 0
        self._total_short_circuits: int = 0

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may transition on read if recovery timeout passed)."""
        if self._state == CircuitState.open:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                return CircuitState.half_open
        return self._state

    @property
    def metrics(self) -> dict[str, Any]:
        """Observability metrics for this breaker."""
        return {
            "provider": self.provider,
            "state": self.state.value,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_short_circuits": self._total_short_circuits,
            "recent_failures": len(self._failure_timestamps),
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }

    def _prune_old_failures(self) -> None:
        """Remove failure timestamps outside the rolling window."""
        cutoff = time.monotonic() - self.failure_window
        while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
            self._failure_timestamps.popleft()

    def _record_failure(self) -> None:
        """Record a failure and potentially trip the breaker."""
        now = time.monotonic()
        self._failure_timestamps.append(now)
        self._last_failure_time = now
        self._total_failures += 1
        self._prune_old_failures()

        if len(self._failure_timestamps) >= self.failure_threshold:
            if self._state != CircuitState.open:
                log.warning(
                    "circuit_breaker_opened",
                    provider=self.provider,
                    failures=len(self._failure_timestamps),
                    threshold=self.failure_threshold,
                )
            self._state = CircuitState.open
            self._half_open_successes = 0

    def _record_success(self) -> None:
        """Record a success — may close the breaker if in half_open."""
        if self._state == CircuitState.half_open:
            self._half_open_successes += 1
            if self._half_open_successes >= self.success_threshold:
                log.info("circuit_breaker_closed", provider=self.provider)
                self._state = CircuitState.closed
                self._failure_timestamps.clear()
                self._half_open_successes = 0
        elif self._state == CircuitState.closed:
            # Successful calls in closed state prune the failure window
            self._prune_old_failures()

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute an async function through the circuit breaker.

        Args:
            func: The async callable to invoke (e.g., ilmu_client.chat.completions.create).
            *args, **kwargs: Passed to func.

        Returns:
            The result of func(*args, **kwargs).

        Raises:
            CircuitOpenError: If the circuit is open and recovery timeout hasn't passed.
            Exception: Re-raises the original exception from func on failure.
        """
        async with self._lock:
            current_state = self.state
            self._total_calls += 1

            if current_state == CircuitState.open:
                self._total_short_circuits += 1
                time_until_probe = self.recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(self.provider, max(0.0, time_until_probe))

            # Allow the call (CLOSED or HALF_OPEN)
            if current_state == CircuitState.half_open:
                self._state = CircuitState.half_open  # explicit state set

        # Execute outside the lock so we don't block other callers
        try:
            result = await func(*args, **kwargs)
        except Exception:
            async with self._lock:
                self._record_failure()
            raise

        async with self._lock:
            self._record_success()
        return result

    def reset(self) -> None:
        """Manually reset the breaker to closed state.

        Useful for admin endpoints or after a provider confirms recovery.
        """
        self._state = CircuitState.closed
        self._failure_timestamps.clear()
        self._half_open_successes = 0
        log.info("circuit_breaker_manual_reset", provider=self.provider)


# ── Global breaker instances (one per LLM provider) ───────────────────────────

_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(
    provider: str,
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> CircuitBreaker:
    """Get or create a circuit breaker for a provider.

    Singleton per provider name — calling get_breaker("ilmu") twice returns
    the same instance.
    """
    if provider not in _breakers:
        _breakers[provider] = CircuitBreaker(
            provider,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
    return _breakers[provider]


def get_all_breaker_metrics() -> list[dict[str, Any]]:
    """Return metrics for all registered breakers (for /health endpoint)."""
    return [b.metrics for b in _breakers.values()]


def reset_all_breakers() -> None:
    """Reset all breakers to closed state. For testing/admin use only."""
    for b in _breakers.values():
        b.reset()


# Pre-register known providers so they're available at import time.
# The actual thresholds can be tuned via get_breaker() kwargs if needed.
ilmu_breaker = get_breaker("ilmu", failure_threshold=5, recovery_timeout=60.0)
anthropic_breaker = get_breaker("anthropic", failure_threshold=3, recovery_timeout=90.0)
openai_breaker = get_breaker("openai_embeddings", failure_threshold=5, recovery_timeout=60.0)
