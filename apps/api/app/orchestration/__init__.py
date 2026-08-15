"""Orchestration observability & safety layer.

This package provides the monitoring, safety, and session management
infrastructure for the multi-agent orchestration system:

- telemetry: structured span tracking with ring buffer
- safety: unified output safety scanner (regex-based red-flag detection)
- metrics: per-agent performance counters and latency histograms
- session_manager: TTL-based cleanup of abandoned agent sessions
"""
"""Multi-agent orchestration layer for NakTahu AI.

This package provides the foundation for coordinating multiple vertical agents:
- AgentProtocol: abstract interface all agents implement
- OrchestratorContext: shared context passed to agents
- AgentResult/AgentStatus: standardized return types
- CircuitBreaker: per-provider resilience wrapper (wraps router_node/
  guard_node's ILMU classification calls — see circuit_breaker.py)
- Enhanced registry: versioned agent definitions with capability vectors

A Redis-backed cross-agent ContextBus previously lived here. Removed: it
was write-only (published to on every orchestration run, cleared at the
end) but had no reader anywhere in the codebase — cross-group context
sharing in the orchestrator was, and still is, done via the in-process
`shared_findings` accumulator in executor_node.py, not this bus. Found
during a full-codebase complexity trace; the Redis round-trips were
overhead with nothing consuming them.
"""

from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentResult, AgentStatus, AgentCapability

__all__ = [
    "AgentProtocol",
    "OrchestratorContext",
    "AgentResult",
    "AgentStatus",
    "AgentCapability",
]
