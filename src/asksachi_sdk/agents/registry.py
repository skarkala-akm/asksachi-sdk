"""In-process registry of workflow ids → agent implementations."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

log = logging.getLogger(__name__)


@runtime_checkable
class Agent(Protocol):
    """One ``complete_chat`` / ``stream_chat`` per HTTP request. AskSachi routes to exactly
    one registered agent and returns its result — orchestration is the agent's concern.

    Optional: implement ``async def is_alive(self) -> bool`` so :meth:`AgentRegistry.list_agents_for_ui`
    can hide the workflow when the backing service is down (e.g. remote A2A server).
    """

    id: str
    title: str
    description: str
    version: str
    execution_mode: str

    async def complete_chat(self, req: Any) -> dict[str, Any]: ...
    async def stream_chat(self, req: Any) -> AsyncIterator[str]: ...


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.id] = agent

    def get(self, workflow_id: str) -> Agent | None:
        return self._agents.get(workflow_id)

    @staticmethod
    def _agent_row(agent: Agent) -> dict[str, str]:
        return {
            "id": agent.id,
            "title": agent.title,
            "description": agent.description,
            "version": agent.version,
            "execution_mode": agent.execution_mode,
        }

    def deregister(self, workflow_id: str) -> bool:
        """Remove *workflow_id* from the registry. Returns ``True`` if it was present."""
        if workflow_id in self._agents:
            del self._agents[workflow_id]
            return True
        return False

    def list_agents(self) -> list[dict[str, str]]:
        """All registered agents (no liveness probe). Tests and admin tools use this."""
        rows = [self._agent_row(a) for a in self._agents.values()]
        return sorted(rows, key=lambda r: r["id"])

    async def list_agents_for_ui(self) -> list[dict[str, str]]:
        """Agents to show in the gateway UI / ``GET /v1/agents`` — skips entries whose ``is_alive`` is false.

        Liveness probes run concurrently so one slow remote agent does not stall the list.
        """
        agents = sorted(self._agents.values(), key=lambda x: x.id)

        async def _is_visible(a: Agent) -> Agent | None:
            probe = getattr(a, "is_alive", None)
            if probe is None:
                return a
            try:
                if await probe():
                    return a
                log.debug("agent_listing_skipped_dead agent_id=%s", a.id)
            except Exception:
                log.warning("agent_listing_liveness_failed agent_id=%s", a.id, exc_info=True)
            return None

        results = await asyncio.gather(*[_is_visible(a) for a in agents])
        return [self._agent_row(a) for a in results if a is not None]
