from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


FINAL_ANSWER_INSTRUCTION = (
    "Answer the original request now using only the MCP results already "
    "provided. Do not request another tool. Be concise and factual."
)
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
    ) -> None:
        self._chat = chat

    async def answer(self, messages: list[dict[str, Any]]) -> str:
        final_messages = [
            *messages,
            {"role": "user", "content": FINAL_ANSWER_INSTRUCTION},
        ]
        response = await self._chat(final_messages, [])
        return str(response.get("content") or DEFAULT_FINAL_ANSWER)


__all__ = [
    "DEFAULT_FINAL_ANSWER",
    "FINAL_ANSWER_INSTRUCTION",
    "FinalAnswerCoordinator",
]
