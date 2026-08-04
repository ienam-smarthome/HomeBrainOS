from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from evidence_recorder import EvidenceRecorder
from mcp_agent_orchestrator import AgentOutcome


class DirectOutcomeContext:
    """Own request-local context setup and cleanup for deterministic outcomes."""

    def __init__(
        self,
        evidence: EvidenceRecorder,
        choices: ContextVar[list[str] | None],
        mutation_call_seen: ContextVar[bool],
        request_class: ContextVar[str],
    ) -> None:
        self._evidence = evidence
        self._choices = choices
        self._mutation_call_seen = mutation_call_seen
        self._request_class = request_class

    async def run(
        self,
        operation: Callable[[], Awaitable[str]],
        *,
        request_class: str,
    ) -> AgentOutcome:
        evidence_token = self._evidence.begin()
        choices_token = self._choices.set([])
        mutation_token = self._mutation_call_seen.set(request_class == "write")
        class_token = self._request_class.set(request_class)
        try:
            message = await operation()
            return AgentOutcome(
                message=message,
                request_class=request_class,
                evidence=self._evidence.receipts(),
                choices=list(self._choices.get() or []),
            )
        finally:
            self._request_class.reset(class_token)
            self._mutation_call_seen.reset(mutation_token)
            self._evidence.reset(evidence_token)
            self._choices.reset(choices_token)


__all__ = ["DirectOutcomeContext"]
