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
- ContextBus: Redis-backed inter-agent state sharing
- CircuitBreaker: per-provider resilience wrapper
- Enhanced registry: versioned agent definitions with capability vectors
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
