"""ContextBus — Redis-backed inter-agent state sharing.

Allows agents running within the same orchestration session to share
intermediate findings without requiring direct coupling. The orchestrator's
executor writes agent outputs to the bus; dependent agents read shared
context before starting.

Design:
- Keyed by correlation_id (the orchestration-level session, NOT individual
  agent session IDs). All agents in one orchestration run share the same
  correlation namespace.
- Data is JSON-serialized and stored with a TTL (default 30 min) to prevent
  unbounded growth from abandoned orchestrations.
- Read-after-write consistency is guaranteed by Redis single-key semantics.
- The bus is opt-in: agents that don't need sibling findings just ignore it.

Usage pattern (from the orchestrator executor):
    bus = ContextBus(redis)
    # After agent A completes:
    await bus.publish_agent_output(corr_id, "grant-finder", result.structured_output)
    # Before starting agent B (which depends on A):
    shared = await bus.get_all_agent_outputs(corr_id)
    context = OrchestratorContext(..., shared_findings=tuple(shared))
"""
from __future__ import annotations

import json
from typing import Any, Optional

import structlog

log = structlog.get_logger(__name__)

_DEFAULT_TTL = 1800  # 30 minutes
_KEY_PREFIX = "orchestration:ctx"


class ContextBus:
    """Redis-backed inter-agent context sharing for orchestration sessions."""

    def __init__(self, redis_client: Any, ttl: int = _DEFAULT_TTL) -> None:
        """Initialize with an async Redis client.

        Args:
            redis_client: redis.asyncio client (from app.state.redis).
            ttl: Time-to-live in seconds for context keys.
        """
        self._redis = redis_client
        self._ttl = ttl

    @property
    def available(self) -> bool:
        """Whether the bus has a working Redis connection."""
        return self._redis is not None

    def _agent_key(self, correlation_id: str, agent_name: str) -> str:
        """Redis key for a specific agent's output in an orchestration."""
        return f"{_KEY_PREFIX}:{correlation_id}:agents:{agent_name}"

    def _meta_key(self, correlation_id: str) -> str:
        """Redis key for orchestration metadata (plan, timestamps)."""
        return f"{_KEY_PREFIX}:{correlation_id}:meta"

    def _agents_set_key(self, correlation_id: str) -> str:
        """Redis SET tracking which agents have published output."""
        return f"{_KEY_PREFIX}:{correlation_id}:published"

    async def publish_agent_output(
        self,
        correlation_id: str,
        agent_name: str,
        output: dict[str, Any],
    ) -> None:
        """Publish an agent's structured output to the shared bus.

        Called by the orchestrator executor after an agent completes.
        Dependent agents can then read this via get_agent_output() or
        get_all_agent_outputs().
        """
        if not self.available:
            log.debug("context_bus_unavailable_skip_publish", agent=agent_name)
            return

        key = self._agent_key(correlation_id, agent_name)
        set_key = self._agents_set_key(correlation_id)

        try:
            payload = json.dumps({"agent": agent_name, "output": output})
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.set(key, payload, ex=self._ttl)
                pipe.sadd(set_key, agent_name)
                pipe.expire(set_key, self._ttl)
                await pipe.execute()
            log.debug("context_bus_published", correlation_id=correlation_id[:8], agent=agent_name)
        except Exception as exc:
            log.warning("context_bus_publish_failed", agent=agent_name, error=str(exc))

    async def get_agent_output(
        self,
        correlation_id: str,
        agent_name: str,
    ) -> Optional[dict[str, Any]]:
        """Retrieve a specific agent's output from the bus.

        Returns None if the agent hasn't published or Redis is unavailable.
        """
        if not self.available:
            return None

        key = self._agent_key(correlation_id, agent_name)
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            return data.get("output")
        except Exception as exc:
            log.warning("context_bus_get_failed", agent=agent_name, error=str(exc))
            return None

    async def get_all_agent_outputs(
        self,
        correlation_id: str,
    ) -> list[dict[str, Any]]:
        """Retrieve all published agent outputs for an orchestration.

        Returns a list of {"agent": name, "output": {...}} dicts, ordered
        by agent name for determinism.
        """
        if not self.available:
            return []

        set_key = self._agents_set_key(correlation_id)
        try:
            agents = await self._redis.smembers(set_key)
            if not agents:
                return []

            results: list[dict[str, Any]] = []
            for agent_name in sorted(agents):
                key = self._agent_key(correlation_id, agent_name)
                raw = await self._redis.get(key)
                if raw:
                    data = json.loads(raw)
                    results.append(data)
            return results
        except Exception as exc:
            log.warning("context_bus_get_all_failed", error=str(exc))
            return []

    async def set_metadata(
        self,
        correlation_id: str,
        metadata: dict[str, Any],
    ) -> None:
        """Store orchestration-level metadata (execution plan, user context).

        Useful for the orchestrator to persist its decomposition plan so
        status checks can report overall progress.
        """
        if not self.available:
            return

        key = self._meta_key(correlation_id)
        try:
            await self._redis.set(key, json.dumps(metadata), ex=self._ttl)
        except Exception as exc:
            log.warning("context_bus_set_meta_failed", error=str(exc))

    async def get_metadata(self, correlation_id: str) -> Optional[dict[str, Any]]:
        """Retrieve orchestration metadata."""
        if not self.available:
            return None

        key = self._meta_key(correlation_id)
        try:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            log.warning("context_bus_get_meta_failed", error=str(exc))
            return None

    async def clear(self, correlation_id: str) -> None:
        """Remove all data for an orchestration session.

        Called on completion or cancellation to free memory immediately
        rather than waiting for TTL expiry.
        """
        if not self.available:
            return

        set_key = self._agents_set_key(correlation_id)
        try:
            agents = await self._redis.smembers(set_key)
            keys_to_delete = [
                self._agent_key(correlation_id, a) for a in (agents or [])
            ]
            keys_to_delete.extend([set_key, self._meta_key(correlation_id)])
            if keys_to_delete:
                await self._redis.delete(*keys_to_delete)
            log.debug("context_bus_cleared", correlation_id=correlation_id[:8])
        except Exception as exc:
            log.warning("context_bus_clear_failed", error=str(exc))
