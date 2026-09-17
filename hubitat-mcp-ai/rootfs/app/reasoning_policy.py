"""Generic model-loop evidence review policy.

This module deliberately contains no user-question grammar. It tracks only the
shape of the model's current tool round and supplies stable instructions for
reasoning over already-gathered evidence. Domain adapters remain authoritative
for facts, arithmetic, safety, and verification; the model is responsible for
understanding the user's whole objective and deciding whether the available
evidence is sufficient to answer it.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any


EVIDENCE_REVIEW_INSTRUCTION = (
    "HOST EVIDENCE-REVIEW CONTRACT: Treat this tool result as evidence, not "
    "automatically as the finished answer. Re-read the user's original request "
    "and all evidence gathered this turn. Check that every material part is "
    "supported. If material evidence is still missing, call the most relevant "
    "declared read tool; do not call extra tools merely to be thorough. When the "
    "evidence is sufficient, synthesize it instead of dumping raw fields. "
    "Distinguish direct observations and deterministic calculations from "
    "inference, state material uncertainty or incomplete coverage, and never "
    "present correlation as proven causation. Do not reveal hidden reasoning."
)

FINAL_SYNTHESIS_INSTRUCTION = (
    "Answer the original request now using only the MCP results already provided "
    "and the evidence already gathered. Do not request another tool. Cover every "
    "material part that the evidence supports. Synthesize the evidence instead "
    "of repeating raw tool output; distinguish direct observations and "
    "deterministic calculations from inference, state material uncertainty or "
    "incomplete coverage, and never present correlation as proven causation. Be "
    "concise and do not reveal hidden reasoning."
)

# The transport sees the complete native function-calling response before the
# orchestrator executes it. Keep an immutable request-local snapshot containing
# both the total size of that native round and the exact unclaimed call
# signatures. ToolExecutor claims a signature before executing it. This is more
# robust than a bare boolean/round-size flag: pre-model discovery, direct fast
# paths, resumed confirmations, or a later request cannot accidentally inherit
# "reasoning mode" merely because an earlier model response had tool calls.
_ACTIVE_TOOL_ROUND: ContextVar[tuple[int, tuple[str, ...]]] = ContextVar(
    "homebrain_active_tool_round", default=(0, ())
)

# These tools have deterministic presenters that can return directly from the
# middle of the orchestrator's per-call loop. When the model intentionally asks
# for more than one tool in the same round, that early return would prevent the
# later calls from running. Single-tool rounds keep their deterministic fast
# presentation; multi-tool rounds defer presentation until every declared call
# has had a chance to execute and the model can synthesize the combined evidence.
_MULTI_CALL_PRESENTER_TOOLS = frozenset(
    {
        "homebrain_active_lights",
        "homebrain_active_rooms",
        "homebrain_active_switches",
        "homebrain_home_snapshot",
        "homebrain_hub_info_snapshot",
        "homebrain_control_devices",
    }
)


def _arguments_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _call_signature(name: str, arguments: Any) -> str:
    return json.dumps(
        [str(name or ""), _arguments_object(arguments)],
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


def observe_assistant_message(message: dict[str, Any]) -> int:
    """Record the exact native tool calls in the current model response."""

    calls = message.get("tool_calls")
    signatures: list[str] = []
    if isinstance(calls, list):
        for item in calls:
            if not isinstance(item, dict):
                continue
            function = item.get("function")
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "")
            if not name:
                continue
            signatures.append(_call_signature(name, function.get("arguments") or {}))
    state = (len(signatures), tuple(signatures))
    _ACTIVE_TOOL_ROUND.set(state)
    return state[0]


def active_tool_round_size() -> int:
    """Return the total current model round size while calls remain unclaimed."""

    total, remaining = _ACTIVE_TOOL_ROUND.get()
    return max(0, int(total)) if remaining else 0


def model_evidence_review_active() -> bool:
    """True while at least one exact model-emitted tool call remains unclaimed."""

    return active_tool_round_size() > 0


def claim_model_tool_call(name: str, arguments: dict[str, Any]) -> int:
    """Claim one exact model-emitted call and return its original round size.

    Non-model executions return zero and do not consume unrelated state. The
    immutable replacement prevents mutable ContextVar values from leaking across
    copied async contexts.
    """

    total, remaining = _ACTIVE_TOOL_ROUND.get()
    if not remaining:
        return 0
    signature = _call_signature(name, arguments)
    try:
        index = remaining.index(signature)
    except ValueError:
        return 0
    next_remaining = remaining[:index] + remaining[index + 1 :]
    _ACTIVE_TOOL_ROUND.set((total, next_remaining))
    return max(0, int(total))


def should_defer_deterministic_presentation(
    tool_name: str,
    data: Any,
    *,
    round_size: int | None = None,
) -> bool:
    """Defer only a multi-call presenter's early return.

    A control ambiguity deliberately remains deterministic: if a control tool
    returned explicit choices, HomeBrain should ask for that clarification rather
    than burying it in a synthesized answer. Sensitive writes never reach this
    function before confirmation, and confirmed executions happen outside an
    active model tool round.
    """

    size = active_tool_round_size() if round_size is None else max(0, int(round_size))
    if size <= 1 or tool_name not in _MULTI_CALL_PRESENTER_TOOLS:
        return False
    if tool_name == "homebrain_control_devices" and isinstance(data, dict):
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            return False
    return True


__all__ = [
    "EVIDENCE_REVIEW_INSTRUCTION",
    "FINAL_SYNTHESIS_INSTRUCTION",
    "active_tool_round_size",
    "claim_model_tool_call",
    "model_evidence_review_active",
    "observe_assistant_message",
    "should_defer_deterministic_presentation",
]
