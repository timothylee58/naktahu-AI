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
