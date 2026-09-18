from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from evidence_ledger import build_current_turn_evidence_ledger
from reasoning_policy import FINAL_SYNTHESIS_INSTRUCTION


FINAL_ANSWER_INSTRUCTION = FINAL_SYNTHESIS_INSTRUCTION
DEFAULT_FINAL_ANSWER = "The MCP request completed without a written answer."


class FinalAnswerCoordinator:
    """Request a bounded final answer after tool execution has finished.

    The coordinator owns the no-more-tools instruction and fallback wording.
    Message budgeting and provider transport remain with the injected chat
    callable so this component cannot bypass the agent's context policy.
    """

    def __init__(
        self,
        chat: Callable[
            [list[dict[str, Any]], list[dict[str, Any]]],
            Awaitable[dict[str, Any]],
        ],
        evidence_supplier: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._chat = chat
        self._evidence_supplier = evidence_supplier

    async def answer(self, messages: list[dict[str, Any]]) -> str:
        ledger = None
        if self._evidence_supplier is not None:
            ledger = build_current_turn_evidence_ledger(
                list(self._evidence_supplier() or [])
            )
        final_messages = [*messages]
        if ledger:
            final_messages.append({"role": "user", "content": ledger})
        final_messages.append(
            {"role": "user", "content": FINAL_ANSWER_INSTRUCTION}
        )
        response = await self._chat(final_messages, [])
        return str(response.get("content") or DEFAULT_FINAL_ANSWER)


__all__ = [
    "DEFAULT_FINAL_ANSWER",
    "FINAL_ANSWER_INSTRUCTION",
    "FinalAnswerCoordinator",
]
