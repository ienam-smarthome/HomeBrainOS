from __future__ import annotations

from typing import Any

from final_answer_coordinator import FinalAnswerCoordinator
from mcp_agent_orchestrator import AgentOutcome, UnifiedMCPAgent as BaseUnifiedMCPAgent


class UnifiedMCPAgent(BaseUnifiedMCPAgent):
    """Production agent with final synthesis delegated to its coordinator."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.final_answers = FinalAnswerCoordinator(self._chat)

    async def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        return await self.final_answers.answer(messages)


__all__ = ["AgentOutcome", "UnifiedMCPAgent"]
