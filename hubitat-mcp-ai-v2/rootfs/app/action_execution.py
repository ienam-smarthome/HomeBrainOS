"""Source-grounded device-command lifecycle and fail-closed answer correction.

This module never chooses a controller, authorizes a write, or interprets
an unspecified domain effect. It classifies *original* in-request MCP
receipts to prevent a model from claiming an unexecuted native operation
succeeded. Physical/router enforcement is never inferred from dispatch.
"""
from __future__ import annotations

import json
import re
from typing import Any


_ACTION_TOOL = "hub_call_device_command"
_DISPATCHED = {"submitted", "native_result", "outcome_unknown"}


def _native_objects(value: Any, depth: int = 0):
    """Yield JSON objects directly and in common MCP content-text wrappers."""
    if depth > 6:
        return
    if isinstance(value, dict):
        yield value
        for key in ("mcp_result", "content", "text"):
            if key in value:
                yield from _native_objects(value[key], depth + 1)
    elif isinstance(value, list):
        for item in value[:40]:
            yield from _native_objects(item, depth + 1)
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return
        if isinstance(parsed, (dict, list)):
            yield from _native_objects(parsed, depth + 1)


def _explicit_native_result(receipt: dict) -> str:
    """Classify top-level native command success separately from waitFor."""
    if receipt.get("success") is not True:
        return "unknown"
    try:
        value = json.loads(receipt.get("response", ""))
    except (TypeError, ValueError):
        return "unknown"
    native = list(_native_objects(value))
    # The client's wrapper often includes client_... scope metadata;
    # 'success' here must come from the original native result.
    flags = [
        obj["success"] for obj in native
        if isinstance(obj.get("success"), bool)
        and not any(str(k).startswith("client_") for k in obj)
    ]
    if False in flags or any(obj.get("isError") is True for obj in native):
        return "rejected"
    if True in flags:
        return "accepted"
    return "reported_response_without_explicit_acceptance"


def _native_reported_attribute(receipts: list[dict], device_id: str,
                               attribute: str, after: int = -1) -> Any:
    """Original same-device attribute from a returned native read (not a proxy)."""
    if not device_id or not attribute:
        return None
    for i in range(len(receipts) - 1, after, -1):
        row = receipts[i]
        if row.get("success") is not True:
            continue
        if row.get("name") not in ("hub_get_device", "hub_get_device_attribute"):
            continue
        args = row.get("arguments", {})
        if str(args.get("deviceId")) != str(device_id):
            continue
        try:
            original = json.loads(row.get("response", ""))
        except (TypeError, ValueError):
            continue
        for obj in _native_objects(original):
            attrs = obj.get("attributes")
            if isinstance(attrs, list):
                for entry in attrs:
                    if isinstance(entry, dict) and entry.get("name") == attribute:
                        return entry.get("value")
            if (obj.get("attribute") == attribute
                    and ("value" in obj or "currentValue" in obj)):
                return obj.get("value", obj.get("currentValue"))
            if isinstance(obj.get("currentStates"), dict):
                if attribute in obj["currentStates"]:
                    return obj["currentStates"][attribute]
    return None


def action_receipt_status(receipts: list[dict]) -> dict[str, Any]:
    """Evidence status of the *bounded native device-command continuation*.

    Never says the physical result was verified by the router; postcondition
    evidence is only a native source-reported value. A transport success is
    not itself a device-effect confirmation.
    """
    calls = [(i, row) for i, row in enumerate(receipts)
             if row.get("name") == _ACTION_TOOL]
    commands = [(i, row) for i, row in calls
                if row.get("dispatch_state") in _DISPATCHED]
    if not commands:
        return {
            "state": "pre_dispatch_rejected" if calls else "not_attempted",
            "native_command_submitted": False,
            "native_acceptance": "not_applicable",
            "postcondition_reported": False,
            "preflight_rejections": sum(
                r.get("dispatch_state") == "preflight_rejected" for _, r in calls),
            "last_error": (calls[-1][1].get("error") if calls else None),
        }
    i, row = commands[0]
    args = row.get("arguments") if isinstance(row.get("arguments"), dict) else {}
    wait = args.get("waitFor") if isinstance(args.get("waitFor"), dict) else {}
    expected = wait.get("expectedValue")
    attr = wait.get("attribute")
    reported = _native_reported_attribute(
        receipts, str(args.get("deviceId", "")), str(attr or ""), after=i)
    comparison = (reported is not None and expected is not None
                  and str(reported).lower() == str(expected).lower())
    acceptance = _explicit_native_result(row)
    if row.get("success") is False:
        state = "outcome_unknown"
    elif acceptance == "rejected":
        state = "native_rejected"
    elif acceptance == "accepted":
        state = "native_accepted"
    else:
        state = "submitted_unconfirmed"
    wait_outcome = row.get("native_wait_for_outcome")
    return {
        "state": state,
        "native_command_submitted": True,
        "native_acceptance": acceptance,
        "device_id": args.get("deviceId"),
        "command": args.get("command"),
        "wait_for_outcome": wait_outcome,
        "postcondition_reported": bool(comparison or wait_outcome == "converged"),
        "postcondition_source": (
            "native_readback" if comparison else
            "original_waitFor" if wait_outcome == "converged" else None
        ),
        "reported_attribute": attr if comparison else None,
        "reported_value": reported if comparison else None,
        "preflight_rejections": sum(
            r.get("dispatch_state") == "preflight_rejected" for _, r in calls),
        "last_error": row.get("error"),
    }


# Only unequivocal claims that the assistant PERFORMED a state-changing
# action; "the switch is still blocked", "I cannot unblock" and "already
# unblocked" are not proof of a newly completed operation.
_EXECUTED_CLAIM = re.compile(
    r"\b(?:i|we)\s+(?:(?:have|had)\s+)?(?:just\s+|successfully\s+)?"
    r"(?:sent|issued|executed|performed|applied|completed|unblocked|blocked|"
    r"enabled|disabled|switched|turned|opened|closed|started|stopped)\b|"
    r"\b(?:has|have|was|were)\s+(?:now\s+)?(?:been\s+)?"
    r"(?:successfully\s+)?(?:unblocked|blocked|enabled|disabled|"
    r"turned\s+(?:on|off)|switched|opened|closed|completed|executed|applied)\b|"
    r"^\s*(?:done|completed successfully|successfully completed)[.!\s]*$",
    re.IGNORECASE | re.MULTILINE,
)


def safe_action_answer(draft: str, summary: dict[str, Any]) -> tuple[str, bool]:
    """Replace only a positive action claim disproven by original receipts.

    Even a native 'accepted' response is not a measured physical transition.
    We retain useful model reasoning if it does not assert execution.
    """
    if not isinstance(draft, str) or not _EXECUTED_CLAIM.search(draft):
        return draft, False
    state = summary.get("state")
    if state in ("not_attempted", "pre_dispatch_rejected"):
        last = str(summary.get("last_error") or "").strip()
        reason = (f" The last local error was: {last}." if last else "")
        return (
            "I could not confirm completion of the requested action. "
            "No native device command was sent to Hubitat during this "
            "request." + reason + " The target's current state has not "
            "been verified as changed."
        ), True
    if state in ("native_rejected", "outcome_unknown", "submitted_unconfirmed"):
        message = (
            "The requested device command was submitted to the native MCP "
            "connection, but its acceptance or resulting effect was not "
            "confirmed. Do not assume the target changed, and do not "
            "automatically retry this potentially executed operation."
        )
        if state == "native_rejected":
            message = (
                "The native MCP response rejected the submitted device "
                "command. The requested change was not confirmed. "
                "No automatic retry was performed."
            )
        return message, True
    if state == "native_accepted" and not summary.get("postcondition_reported"):
        return (
            "The native MCP server reported accepting the device command, "
            "but the requested target-state change was not verified by "
            "a matching postcondition in the returned evidence. "
            "Physical execution remains unconfirmed."
        ), True
    return draft, False
