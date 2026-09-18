"""Generic model-loop evidence review and bounded reasoning policy.

This module deliberately contains no user-question grammar. It tracks only the
shape of the model's current tool round and the amount of model-directed read
work performed in the current request. Domain adapters remain authoritative for
facts, arithmetic, safety, and verification; the model is responsible for
understanding the user's whole objective and deciding whether the available
current-turn evidence is sufficient to answer it.
"""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from typing import Any

from request_metrics import active_request_identity


CURRENT_TURN_EVIDENCE_RULE = (
    "CURRENT-TURN EVIDENCE BOUNDARY: Conversation history is context only, not "
    "proof of a live or historical fact in this request. Never repeat or rely on "
    "a previous assistant factual claim unless a tool result from THIS request "
    "independently supports it. If the current-turn tools do not establish a "
    "requested fact, say that the available evidence does not establish it."
)

EVIDENCE_REVIEW_INSTRUCTION = (
    "HOST EVIDENCE-REVIEW CONTRACT: Treat this tool result as evidence, not "
    "automatically as the finished answer. Re-read the user's original request "
    "and all CURRENT-TURN tool evidence gathered so far. Conversation history is "
    "context only and must not be treated as evidence for a live or historical "
    "claim. Check that every material part is supported. If material evidence is "
    "still missing, call the most relevant declared read tool; do not call extra "
    "tools merely to be thorough and do not re-read the same fact in a different "
    "form. Do not investigate a cause for an event until current-turn evidence "
    "establishes that the event actually occurred in the requested window. When "
    "the evidence is sufficient, synthesize it instead of dumping raw fields. "
    "Distinguish direct observations and deterministic calculations from "
    "inference, state material uncertainty or incomplete coverage, and never "
    "present correlation as proven causation. For device history, page/source "
    "coverage does not prove the event stream contains every physical transition; "
    "when history source integrity is unverified, do not claim an exact duration, "
    "continuity, or absence from missing rows. Do not reveal hidden reasoning."
)

FINAL_SYNTHESIS_INSTRUCTION = (
    "Answer the original request now using only the MCP results already provided "
    "from the CURRENT TURN and the evidence already gathered in this turn. "
    "Conversation history is context only and is not evidence for a live or "
    "historical factual claim. Do not request another tool. Cover every material "
    "part that the current-turn evidence supports; if a requested fact is not "
    "established by current-turn evidence, say so instead of copying an earlier "
    "assistant claim. Synthesize the evidence instead of repeating raw tool "
    "output; distinguish direct observations and deterministic calculations from "
    "inference, state material uncertainty or incomplete coverage, and never "
    "present correlation as proven causation. For device history, treat page "
    "completeness separately from event-stream integrity; if integrity is "
    "unverified, describe recorded-event estimates without claiming exact totals, "
    "continuity, or absence. Be concise and do not reveal hidden reasoning."
)

# 0.10.453 proved that open-ended read investigations can become materially more
# useful, but live tests also showed runaway evidence gathering (19-30 calls and
# 5-7 model rounds). These are soft READ budgets, not action budgets. Writes and
# confirmation flows are never blocked by this policy. Once the budget is spent,
# HomeBrain keeps the evidence it already gathered and forces one synthesis turn.
DEFAULT_MAX_READ_TOOL_CALLS = 8
DEFAULT_MAX_READ_TOOL_ROUNDS = 3

# Legacy 0.10.447 causal prompting told the model to hunt related room sensors.
# The 0.10.453 generic evidence contract supersedes it. Transport normalization
# removes this old message if an older orchestrator path still appends it, so
# causal investigation is governed by the same bounded policy as every other read.
LEGACY_CAUSAL_HINT_PREFIX = "HOST CAUSAL-INVESTIGATION HINT"

# The WebUI's clarification follow-up is explicit host metadata, not natural
# language intent: ``Device clarification: use exactly <label>.``. Preserve that
# choice as a request-local hard constraint so a model cannot fan back out across
# the alternatives the user just resolved. Only named local resolution/history
# reads are constrained; unrelated evidence such as location events or rule lists
# remains available when it is genuinely needed.
_SELECTION_MARKER = re.compile(
    r"^\s*Device clarification:\s*use exactly\s+(?P<label>.+?)\s*[.!]?\s*$",
    re.I | re.M,
)
_BOUND_SELECTED_TOOLS = frozenset({
    "homebrain_device_history",
    "homebrain_resolve_device",
})
_SELECTED_TARGET: ContextVar[str | None] = ContextVar(
    "homebrain_selected_reasoning_target", default=None
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

# (request identity, tool rounds, executed read calls, mutation seen, skipped reads)
_REASONING_BUDGET: ContextVar[tuple[object | None, int, int, bool, int]] = ContextVar(
    "homebrain_reasoning_budget", default=(None, 0, 0, False, 0)
)

# A cause/trigger investigation may discover controller candidates only on the
# third (normally final) read round. Preserve exactly one bounded opportunity to
# inspect one of those controller histories rather than forcing synthesis before
# the newly discovered stronger evidence can be read.
_CONTROLLER_FOLLOWUP: ContextVar[
    tuple[object | None, tuple[tuple[str, tuple[str, ...]], ...], bool] | None
] = ContextVar("homebrain_controller_followup", default=None)

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


def _budget_state() -> tuple[object | None, int, int, bool, int]:
    current_identity = active_request_identity()
    identity, rounds, reads, mutation, skipped = _REASONING_BUDGET.get()
    if current_identity is not None and identity is not current_identity:
        state = (current_identity, 0, 0, False, 0)
        _REASONING_BUDGET.set(state)
        return state
    return identity, rounds, reads, mutation, skipped


def _normalized_target(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _bind_selected_target(messages: list[dict[str, Any]]) -> None:
    """Bind only the current request's explicit clarification marker."""

    target: str | None = None
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = str(message.get("content") or "")
        match = _SELECTION_MARKER.search(content)
        if match is not None:
            candidate = match.group("label").strip()
            target = candidate or None
        break
    _SELECTED_TARGET.set(target)


def selected_reasoning_target() -> str | None:
    return _SELECTED_TARGET.get()


def blocked_selected_target(name: str, arguments: dict[str, Any]) -> str | None:
    """Reject a model read that contradicts an explicit clarification choice."""

    selected = selected_reasoning_target()
    if not selected or name not in _BOUND_SELECTED_TOOLS:
        return None
    requested = str(arguments.get("name") or "").strip()
    if not requested or _normalized_target(requested) == _normalized_target(selected):
        return None
    return (
        f"Not executed: this request explicitly selected {selected!r}. "
        f"Use exactly that device for named history/resolution reads; do not inspect "
        f"the other clarification candidates."
    )


def reset_reasoning_budget() -> None:
    """Reset request reasoning counters.

    Production requests normally reset implicitly from RequestMetrics identity.
    The explicit reset also protects direct/base-agent callers that do not install
    metrics and therefore have no identity token to distinguish consecutive turns.
    """

    _REASONING_BUDGET.set((active_request_identity(), 0, 0, False, 0))
    _ACTIVE_TOOL_ROUND.set((0, ()))
    _SELECTED_TARGET.set(None)
    _CONTROLLER_FOLLOWUP.set(None)


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
    if signatures:
        identity, rounds, reads, mutation, skipped = _budget_state()
        _REASONING_BUDGET.set((identity, rounds + 1, reads, mutation, skipped))
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


def arm_controller_followup_budget(candidates: list[dict[str, Any]]) -> bool:
    """Reserve one extra read opportunity for a newly discovered controller.

    Candidate identity and allowed history attributes are derived from structured
    room-filter output. The reservation is request-local and can be consumed only
    once.
    """

    identity = active_request_identity()
    allowed: list[tuple[str, tuple[str, ...]]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        label = _normalized_target(candidate.get("label"))
        attrs = tuple(
            sorted({
                _normalized_target(value)
                for value in (candidate.get("suggestedHistoryAttributes") or [])
                if _normalized_target(value)
            })
        )
        if label and attrs:
            allowed.append((label, attrs))
    if not allowed:
        return False
    _CONTROLLER_FOLLOWUP.set((identity, tuple(allowed[:8]), False))
    return True


def _controller_followup_state() -> tuple[
    tuple[tuple[str, tuple[str, ...]], ...], bool
] | None:
    state = _CONTROLLER_FOLLOWUP.get()
    if state is None:
        return None
    identity, allowed, consumed = state
    current_identity = active_request_identity()
    if identity is not current_identity:
        _CONTROLLER_FOLLOWUP.set(None)
        return None
    return allowed, consumed


def controller_followup_pending() -> bool:
    state = _controller_followup_state()
    return bool(state is not None and not state[1])


def _consume_controller_followup(
    name: str,
    arguments: dict[str, Any],
) -> bool:
    state = _controller_followup_state()
    if state is None or state[1]:
        return False
    allowed, _consumed = state
    identity = active_request_identity()
    _CONTROLLER_FOLLOWUP.set((identity, allowed, True))

    if name != "homebrain_device_history":
        return False
    requested = _normalized_target(arguments.get("name"))
    attribute = _normalized_target(arguments.get("attribute"))
    if not requested or not attribute:
        return False
    return any(
        requested == label and attribute in attrs
        for label, attrs in allowed
    )


def register_model_tool_execution(
    *,
    name: str = "",
    arguments: dict[str, Any] | None = None,
    mutates: bool,
) -> bool:
    """Reserve one model-directed tool execution under the read budget.

    Returns ``False`` only when a read should be skipped because the current
    request already spent its generic reasoning budget. Mutation calls are always
    allowed and permanently disable read-budget forcing for that request so the
    confirmation/verification safety path is never truncated by this policy.
    """

    identity, rounds, reads, mutation_seen, skipped = _budget_state()
    if mutates:
        _REASONING_BUDGET.set((identity, rounds, reads, True, skipped))
        return True
    if mutation_seen:
        return True
    if reads >= DEFAULT_MAX_READ_TOOL_CALLS:
        if _consume_controller_followup(name, dict(arguments or {})):
            _REASONING_BUDGET.set(
                (identity, rounds, reads + 1, mutation_seen, skipped)
            )
            return True
        _REASONING_BUDGET.set((identity, rounds, reads, mutation_seen, skipped + 1))
        return False
    _REASONING_BUDGET.set((identity, rounds, reads + 1, mutation_seen, skipped))
    return True


def reasoning_budget_exhausted() -> bool:
    """Whether a read-only model investigation should synthesize now."""

    _identity, rounds, reads, mutation_seen, _skipped = _budget_state()
    if mutation_seen or reads <= 0:
        return False
    if controller_followup_pending():
        return False
    return (
        reads >= DEFAULT_MAX_READ_TOOL_CALLS
        or rounds >= DEFAULT_MAX_READ_TOOL_ROUNDS
    )


def reasoning_budget_status() -> dict[str, Any]:
    """Privacy-safe budget state for tests/logging and host instructions."""

    _identity, rounds, reads, mutation_seen, skipped = _budget_state()
    return {
        "toolRounds": rounds,
        "readCalls": reads,
        "mutationSeen": mutation_seen,
        "skippedReadCalls": skipped,
        "maxToolRounds": DEFAULT_MAX_READ_TOOL_ROUNDS,
        "maxReadCalls": DEFAULT_MAX_READ_TOOL_CALLS,
        "controllerFollowupPending": controller_followup_pending(),
        "exhausted": reasoning_budget_exhausted(),
    }


def _add_system_boundary(
    messages: list[dict[str, Any]], boundary: str
) -> list[dict[str, Any]]:
    """Add a host invariant without displacing a more specific trailing hint.

    Target/device/confirmation retry messages intentionally live at the end of the
    transcript. Appending a generic user message after them weakens their recency
    and broke exact retry contracts. Put the invariant in the system message
    instead, preserving both ordering and the last-message semantics.
    """

    prepared = [dict(message) for message in messages]
    for index, message in enumerate(prepared):
        if message.get("role") != "system":
            continue
        content = str(message.get("content") or "")
        if boundary not in content:
            prepared[index] = {**message, "content": content + "\n\n" + boundary}
        return prepared
    return [{"role": "system", "content": boundary}, *prepared]


def _append_final_instruction(
    messages: list[dict[str, Any]], instruction: str
) -> list[dict[str, Any]]:
    """Add final synthesis while preserving an existing trailing user contract."""

    prepared = [dict(message) for message in messages]
    if prepared and prepared[-1].get("role") == "user":
        content = str(prepared[-1].get("content") or "")
        if FINAL_SYNTHESIS_INSTRUCTION in content:
            return prepared
        prepared[-1] = {
            **prepared[-1],
            "content": content + "\n\n" + instruction,
        }
        return prepared
    prepared.append({"role": "user", "content": instruction})
    return prepared


def prepare_reasoning_turn(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize provider input around current-turn evidence and read budgets.

    This is intentionally generic. It does not choose domain tools. It removes
    only the obsolete causal sensor-hunting host hint, reinforces that prior
    conversation is not evidence, binds an explicit host clarification selection,
    and when the soft read budget is spent removes callable tools and requests
    synthesis from the evidence already collected.
    """

    prepared: list[dict[str, Any]] = []
    for message in messages:
        if (
            message.get("role") == "user"
            and str(message.get("content") or "").lstrip().startswith(
                LEGACY_CAUSAL_HINT_PREFIX
            )
        ):
            continue
        prepared.append(dict(message))

    has_tool_message = any(message.get("role") == "tool" for message in prepared)
    # Direct/base-agent callers do not always install RequestMetrics. Their first
    # provider turn is still structurally identifiable: callable tools are present
    # and no current-turn tool result exists yet. Reset here so a prior direct
    # request cannot spend the next request's ContextVar budget.
    if tools and not has_tool_message:
        reset_reasoning_budget()
        _bind_selected_target(prepared)

    selected = selected_reasoning_target()
    if selected:
        prepared = _add_system_boundary(
            prepared,
            "BOUND DEVICE CLARIFICATION: The user already resolved the device "
            f"ambiguity. Use exactly {selected!r} for named device history or "
            "resolution reads in this request. Do not inspect the other prior "
            "clarification candidates unless the user explicitly asks to compare them.",
        )

    status = reasoning_budget_status()
    has_current_tool_evidence = has_tool_message or status["readCalls"] > 0
    if has_current_tool_evidence:
        prepared = _add_system_boundary(prepared, CURRENT_TURN_EVIDENCE_RULE)

    force_synthesis = bool(tools) and reasoning_budget_exhausted()
    outgoing_tools = [] if force_synthesis else list(tools)
    if not outgoing_tools and has_current_tool_evidence:
        final_instruction = FINAL_SYNTHESIS_INSTRUCTION
        if force_synthesis:
            final_instruction += (
                " The host read-reasoning budget is now exhausted; do not ask for "
                "more evidence in this turn."
            )
        prepared = _append_final_instruction(prepared, final_instruction)
    return prepared, outgoing_tools


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
    "CURRENT_TURN_EVIDENCE_RULE",
    "DEFAULT_MAX_READ_TOOL_CALLS",
    "DEFAULT_MAX_READ_TOOL_ROUNDS",
    "EVIDENCE_REVIEW_INSTRUCTION",
    "FINAL_SYNTHESIS_INSTRUCTION",
    "active_tool_round_size",
    "arm_controller_followup_budget",
    "blocked_selected_target",
    "controller_followup_pending",
    "claim_model_tool_call",
    "model_evidence_review_active",
    "observe_assistant_message",
    "prepare_reasoning_turn",
    "reasoning_budget_exhausted",
    "reasoning_budget_status",
    "register_model_tool_execution",
    "reset_reasoning_budget",
    "selected_reasoning_target",
    "should_defer_deterministic_presentation",
]
