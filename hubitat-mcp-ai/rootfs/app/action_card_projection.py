"""Safe, structured UI projection of an already-queued confirmation group.

No free-text prompt parsing, tool execution, approval, write, or re-planning.
The immutable ConfirmedActionCoordinator queue remains authoritative.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from mcp_client import MCPTool
from tool_registry import ToolEffect, classify_tool_effect

_ALLOWED_FIELDS = (
    ("device", frozenset(("deviceId", "device_id", "device", "targets", "targetId"))),
    ("time", frozenset(("atTime", "atTime#", "time", "startTime", "endTime",
                       "scheduledAt", "delayMinutes", "minutes", "atDate", "atDate#"))),
    ("days", frozenset(("days", "weekdays", "daysOfWeek"))),
)
_ALLOWED_COMMAND_KEYS = frozenset(("command", "operation", "action", "tool"))
_SECRET_MARKERS = ("token", "secret", "password", "passphrase", "api_key", "authorization",
                   "credential", "accesskey", "mac", "ipaddress", "pin")
_ALLOWED_EFFECTS = {effect.value for effect in ToolEffect}
_MAX_ACTIONS = 12


def _public_value(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)[:70]
    if isinstance(value, str) and len(value) <= 70:
        return value.strip() or None
    if isinstance(value, list) and 0 < len(value) <= 7:
        parts = [_public_value(part) for part in value]
        return ", ".join(parts) if all(parts) else None
    return None


def _walk(value: object, depth: int = 0) -> Iterable[tuple[str, Any]]:
    if depth > 5:
        return
    if isinstance(value, dict):
        for key, raw in list(value.items())[:50]:
            if not isinstance(key, str):
                continue
            if any(marker in key.casefold().replace("_", "") for marker in _SECRET_MARKERS):
                continue
            yield key, raw
            if isinstance(raw, (dict, list)):
                yield from _walk(raw, depth + 1)
    elif isinstance(value, list):
        for raw in value[:14]:
            if isinstance(raw, (dict, list)):
                yield from _walk(raw, depth + 1)


def queued_action_card(actions: object) -> dict[str, Any] | None:
    """Return a display-safe description of queued, UNEXECUTED native calls.

    A missing or unrecognised operation is shown conservatively, never
    presented as a device effect or silently made directly editable.
    """
    if not isinstance(actions, list) or not 0 < len(actions) <= _MAX_ACTIONS:
        return None
    previews = []
    severity = {ToolEffect.READ.value: 0, ToolEffect.ROUTINE_WRITE.value: 1,
                ToolEffect.SENSITIVE_WRITE.value: 2, ToolEffect.DESTRUCTIVE_WRITE.value: 3}
    for row in actions:
        if not (isinstance(row, (list, tuple)) and len(row) == 2):
            return None
        name, args = row
        if not isinstance(name, str) or not name or not isinstance(args, dict):
            return None
        # Native operation and exact typed parameters, not user text, decide
        # effect. Unknown tools remain conservative sensitive writes.
        effect = classify_tool_effect(MCPTool(name, "", {}), args).value
        if effect not in _ALLOWED_EFFECTS:
            effect = ToolEffect.SENSITIVE_WRITE.value
        if effect == ToolEffect.READ.value:
            # A read may accompany another write in the queued model round.
            previews.append({"tool": name[:100], "effect": effect,
                             "command": "Read-only companion", "fields": []})
            continue
        shown: dict[str, str] = {}
        verb = ""
        for key, raw in _walk(args):
            if key in _ALLOWED_COMMAND_KEYS and not verb:
                verb = _public_value(raw) or ""
            for slot, keys in _ALLOWED_FIELDS:
                if slot not in shown and key in keys:
                    valid = _public_value(raw)
                    if valid:
                        shown[slot] = valid
        previews.append({
            "tool": name[:100],
            "effect": effect,
            "command": verb[:70] or "native operation",
            # Only these fields may become *user-editable proposed text*.
            # Never substitute them into immutable native confirmation args.
            "fields": [{"kind": field, "value": value} for field, value in shown.items()],
        })
    writes = [row for row in previews if row["effect"] != ToolEffect.READ.value]
    if not writes:
        return None
    effect = max((row["effect"] for row in writes), key=lambda e: severity[e])
    return {
        "status": "pending_confirmation",
        "effect_class": effect,
        "action_count": len(actions),
        "actions": previews,
        "summary": (f"{len(writes)} proposed native write"
                    + ("s" if len(writes) != 1 else "")
                    + " — not executed"),
        "approval_command": "confirm",
        "edits_require_new_proposal": True,
        "dry_run_available": False,
        "undo_available": False,
    }
