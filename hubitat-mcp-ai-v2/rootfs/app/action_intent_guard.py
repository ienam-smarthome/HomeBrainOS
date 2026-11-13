"""Conservative authorization boundary between one-shot device actions and rules.

A user asking for an ordinary change AFTER a relative delay has not specified
an independent event trigger or a recurring automation. A native rule write
that invents that trigger would permanently change future behavior. This
module neither discovers actuators nor chooses/sends a device command.
"""
from __future__ import annotations

import re
from typing import Any


_CONFIRMATION_ONLY = re.compile(
    r"^\s*(?:yes|yep|yeah|ok(?:ay)?|confirm|proceed|go ahead|do it)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_DIRECT_ACTION = re.compile(
    r"^\s*(?:please\s+)?(?:turn|switch|set|enable|disable|start|stop|"
    r"block|unblock|allow|deny|open|close|lock|unlock|mute|unmute|"
    r"pause|resume|dim|brighten|increase|decrease|activate|deactivate)\b",
    re.IGNORECASE,
)
_DELAY_ONSET = re.compile(
    r"\b(?:after|in)\s+\d+(?:\.\d+)?\s*"
    r"(?:sec(?:ond)?s?|mins?|minutes?|hours?|hrs?)\b",
    re.IGNORECASE,
)
# An actual separate triggering event, frequency or explicit request to
# define automation belongs to a different category; do not suppress it.
_RECURRING_OR_EVENT = re.compile(
    r"\b(?:whenever|every|each\s+time|once\s+\w+\s+"
    r"(?:starts?|stops?|changes?)|when|if|on\s+(?:motion|mode|presence|"
    r"weekday|weekend|sunrise|sunset)|upon)\b",
    re.IGNORECASE,
)
_EXPLICIT_RULE_REQUEST = re.compile(
    r"\b(?:create|make|edit|update|replace|configure|build|save|set\s+up)\s+"
    r"(?:a\s+|an\s+|the\s+)?(?:new\s+|existing\s+|temporary\s+)?"
    r"(?:rule|automation|routine|schedule)\b",
    re.IGNORECASE,
)
_READONLY = re.compile(
    r"\b(?:do\s+not|don't|never|without)\s+(?:\w+\s+){0,4}"
    r"(?:modify|change|act|execute|send|create|write|touch|run)\b|"
    r"\bread[- ]only\b|\bdry[- ]run\b",
    re.IGNORECASE,
)
_RULE_WRITERS = frozenset({
    "hub_set_visual_rule", "hub_set_rule", "hub_create_custom_rule",
    "hub_update_custom_rule", "hub_set_native_app",
})


def original_one_shot_delay(question: str, history: list[dict] | None) -> str | None:
    """Recognize a narrow direct-onset request, including a simple 'yes' reply.

    For 'yes' we may consult the last actionable user request in this same
    conversation, but never treat archival/tool text as a request. If the
    user subsequently explicitly requested a rule, that is a NEW request
    and this guard does not veto it.
    """
    if not isinstance(question, str):
        return None
    text = question.strip()
    if _CONFIRMATION_ONLY.fullmatch(text):
        for row in reversed(history or []):
            if not isinstance(row, dict) or row.get("role") != "user":
                continue
            candidate = row.get("content")
            if not isinstance(candidate, str):
                continue
            candidate = candidate.strip()
            if not _CONFIRMATION_ONLY.fullmatch(candidate):
                text = candidate
                break
    if (
        _DIRECT_ACTION.match(text)
        and _DELAY_ONSET.search(text)
        and not _RECURRING_OR_EVENT.search(text)
        and not _EXPLICIT_RULE_REQUEST.search(text)
        and not _READONLY.search(text)
    ):
        return text
    return None


def unrequested_rule_write_reason(
    question: str,
    history: list[dict] | None,
    tool_name: str,
    arguments: dict[str, Any] | None,
) -> str | None:
    """Block only a native automation write with NO user-authorized trigger.

    Authorization belongs to the user's original request, not to an
    assistant-proposed rule or a statement in a tool result. Both direct
    rules and selected gateway leaves are checked. This is NOT a general
    prohibition on user-requested automations.
    """
    leaf = (arguments or {}).get("tool")
    writer = leaf if isinstance(leaf, str) else tool_name
    if writer not in _RULE_WRITERS:
        return None
    if original_one_shot_delay(question, history) is None:
        return None
    return (
        "This is an immediate-start, one-off device action with a relative "
        "delay, not a user-requested event-triggered or recurring rule. "
        "The native automation write was NOT sent. Do not invent a trigger "
        "such as a current mode change; activating that rule would not "
        "start the countdown now and may run unexpectedly later. Check "
        "the source-supported ACTUAL actuator's native commands first: "
        "a built-in delayed command may implement the action directly. "
        "If the target is already in the requested final state, do not "
        "reverse it without permission. If no native delayed command can "
        "be verified, state that limitation or ask for the genuinely "
        "missing scheduling/trigger semantics instead of creating a rule."
    )


def rule_activation_outcome(result: Any) -> dict[str, Any] | None:
    """Return rule-specific source flags from an original MCP content envelope.

    Used only for outcome wording, not to authorize/execute a writer.
    """
    import json
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (TypeError, ValueError):
            return None
    if not isinstance(result, dict):
        return None
    if isinstance(result.get("content"), list):
        for item in result["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                parsed = rule_activation_outcome(item.get("text"))
                if parsed:
                    return parsed
    if isinstance(result.get("mcp_result"), dict):
        return rule_activation_outcome(result["mcp_result"])
    if any(k in result for k in ("activated", "activatedSuccessfully", "validationErrors")):
        status = {
            "stored": result.get("storedSuccessfully"),
            "activated": result.get("activatedSuccessfully",
                                    result.get("activated")),
            "validation_errors": result.get("validationErrors") or [],
            "app_id": result.get("appId"),
        }
        return status
    return None
