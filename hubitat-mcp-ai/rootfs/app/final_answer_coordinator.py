from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from evidence_ledger import build_current_turn_evidence_ledger
from investigation_policy import (
    is_causal_investigation,
    is_history_investigation,
)
from reasoning_policy import FINAL_SYNTHESIS_INSTRUCTION
from synthesis_context import build_tool_evidence_packet
from synthesis_validator import validate_synthesis


FINAL_ANSWER_INSTRUCTION = FINAL_SYNTHESIS_INSTRUCTION
DEFAULT_FINAL_ANSWER = "The MCP request completed without a written answer."


def _original_user_request(messages: list[dict[str, Any]]) -> str:
    """Return the most recent non-host user objective."""

    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = str(message.get("content") or "").strip()
        if not content or content.lstrip().startswith("HOST "):
            continue
        return content
    return ""


def _synthesis_instruction(original_user: str) -> str:
    """Build the shared final reasoning contract from request class."""

    causal = is_causal_investigation(original_user)
    investigative = is_history_investigation(original_user)
    if not investigative:
        return FINAL_SYNTHESIS_INSTRUCTION

    text = (
        "Answer the ORIGINAL user request now using only CURRENT-TURN MCP evidence. "
        "Do not request another tool and do not answer a narrower substitute "
        "question merely because one source is easy to summarize. "
    )
    if causal:
        text += (
            "This is a causal investigation. Lead with the best-supported "
            "explanation and calibrate confidence. Reconstruct the important "
            "timeline by correlating timestamps across sources. Separate a likely "
            "trigger/provenance event from downstream automation effects. Explain "
            "what remains unproven or unexplained. Only suggest a configuration "
            "change when the evidence makes it relevant. A device state transition "
            "or close timestamp alone is correlation, not proof of a person or "
            "automation causing it. "
        )
    elif investigative:
        text += (
            "This is an analytical history request. Compare the relevant evidence "
            "classes directly, preserve objective patterns and uncertainty, and do "
            "not invent a causal explanation or normality baseline that the "
            "current-turn evidence does not establish. "
        )
    text += (
        "Synthesize rather than dump raw fields. For unverified device-event "
        "streams, describe durations/counts as recorded-event estimates rather "
        "than exact physical history. Preserve useful supported analysis instead "
        "of reducing the answer to a duration or event list. Be concise but "
        "complete and do not reveal hidden reasoning."
    )
    return text


class FinalAnswerCoordinator:
    """Own the single no-tools reasoning/synthesis path for every agent layer.

    Investigation gathers evidence; this coordinator converts that evidence into
    one model-authored answer, then uses deterministic guards only as validators.
    The production wrapper and base orchestrator intentionally share this class so
    their final-answer behavior cannot diverge.
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
        evidence = (
            list(self._evidence_supplier() or [])
            if self._evidence_supplier is not None
            else []
        )
        original_user = _original_user_request(messages)
        investigative = is_history_investigation(original_user)
        brief = build_current_turn_evidence_ledger(evidence)
        tool_packet = (
            build_tool_evidence_packet(messages)
            if investigative
            else None
        )

        final_messages = [*messages]
        if brief:
            final_messages.append({"role": "user", "content": brief})
        if tool_packet:
            final_messages.append({"role": "user", "content": tool_packet})
        final_messages.append({
            "role": "user",
            "content": _synthesis_instruction(original_user),
        })

        response = await self._chat(final_messages, [])
        draft = str(response.get("content") or DEFAULT_FINAL_ANSWER)
        if not investigative:
            # Simple factual/history answers keep their established one-pass
            # behavior; API serialization still applies local safety guards.
            return draft

        corrected, issues = validate_synthesis(draft, evidence)
        if not issues:
            return draft

        # Validators identify factual conflicts; they do not author the answer.
        # Give the model one no-tools repair pass so supported causal analysis,
        # timelines, and uncertainty survive a local correction.
        repair_messages = [
            *final_messages,
            {"role": "assistant", "content": draft},
            {
                "role": "user",
                "content": (
                    "HOST SYNTHESIS VALIDATION REPAIR\n"
                    f"Detected deterministic issues: {', '.join(issues)}.\n"
                    "Rewrite the draft answer, preserving every supported useful "
                    "explanation, timeline, and uncertainty statement while fixing "
                    "only the factual conflicts. Do not request tools. The following "
                    "is a deterministic localized baseline showing corrections that "
                    "must be respected; it is NOT a replacement answer:\n"
                    + corrected
                ),
            },
        ]
        repaired = await self._chat(repair_messages, [])
        repaired_content = str(repaired.get("content") or "").strip()
        if not repaired_content:
            return corrected

        repaired_corrected, remaining = validate_synthesis(
            repaired_content,
            evidence,
        )
        return repaired_content if not remaining else repaired_corrected


__all__ = [
    "DEFAULT_FINAL_ANSWER",
    "FINAL_ANSWER_INSTRUCTION",
    "FinalAnswerCoordinator",
    "_original_user_request",
    "_synthesis_instruction",
]
