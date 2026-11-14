"""Per-request progress and explicit confirmation for upstream confirm flags."""
from __future__ import annotations

import asyncio
import copy
import json
import uuid

from mcp import MCPError, redact
from action_intent_guard import automation_write_requires_confirmation
from action_proposal_review import is_native_action_proposal


def needs_confirmation(value) -> bool:
    if isinstance(value, dict):
        return any(
            (key == "confirm" and bool(item))
            or needs_confirmation(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(needs_confirmation(item) for item in value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            return False
        if isinstance(decoded, (dict, list)):
            return needs_confirmation(decoded)
    return False


def action_effect_class(name: str, arguments: dict, *, write: bool) -> str:
    """Classify the selected structured native call, never user prose.

    V2 has no V1 ToolEffect registry. Unrecognised native writes remain
    sensitive; all nonwrites are classified by tool metadata.
    """
    if not write:
        return "read"
    leaf = arguments.get("tool") if isinstance(arguments, dict) else None
    selected = leaf if isinstance(leaf, str) else name
    operation = str(arguments.get("operation", "")).lower() if isinstance(arguments, dict) else ""
    if (selected.startswith(("hub_delete_", "hub_restore_", "hub_shutdown"))
            or selected in {"hub_reboot", "hub_reset", "hub_factory_reset"}
            or operation in {"delete", "remove", "purge", "reset", "restore"}):
        return "destructive_write"
    if selected == "hub_call_device_command":
        return "routine_write"
    return "sensitive_write"


def action_preview(name: str, arguments: dict, effect: str) -> dict:
    """Bounded, redacted UI projection. Never reusable as native call args."""
    safe = redact(copy.deepcopy(arguments))
    fields = {}
    def visit(node, depth=0):
        if depth > 3 or not isinstance(node, dict):
            return
        for key, value in node.items():
            if key in {"deviceId", "device_id", "device", "targetId"} and "device" not in fields:
                if isinstance(value, (str, int)):
                    fields["device"] = str(value)[:80]
            elif key in {"atTime", "time", "startTime", "scheduledAt", "delayMinutes", "minutes", "date", "atDate"} and "time" not in fields:
                if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                    fields["time"] = str(value)[:80]
            elif key in {"days", "weekdays", "daysOfWeek"} and "days" not in fields:
                if isinstance(value, str):
                    fields["days"] = value[:90]
                elif isinstance(value, list) and all(isinstance(x, str) for x in value[:8]):
                    fields["days"] = ", ".join(value[:8])[:90]
            elif key in {"args", "settings"} and isinstance(value, dict):
                visit(value, depth+1)
    visit(safe)
    leaf = safe.get("tool") if isinstance(safe, dict) else None
    verb = (safe.get("command") or safe.get("operation")) if isinstance(safe, dict) else None
    if not verb and isinstance(safe.get("args"), dict):
        nested = safe["args"]
        verb = nested.get("command") or nested.get("operation")
    return {"tool": str(leaf or name)[:100],
            "verb": str(verb)[:80] if isinstance(verb, (str, int)) else "Native operation",
            "effect_class": effect,
            "fields": fields}


class Interaction:
    def __init__(self, *, require_native_write_approval: bool = False):
        self.require_native_write_approval = require_native_write_approval
        self.current = None
        self.pending = None
        self._decision = None

    def status(self) -> dict:
        return {"current": self.current, "pending": self.pending}

    def decide(self, approval_id: str, approved: bool) -> None:
        if (not self.pending or self.pending["id"] != approval_id
                or self._decision is None or self._decision.done()):
            raise ValueError("This confirmation is no longer pending")
        self._decision.set_result(approved)

    async def before_call(self, name: str, arguments: dict, explanation: str) -> None:
        self.current = {
            "name": name, "arguments": redact(copy.deepcopy(arguments)),
            "explanation": redact(explanation),
        }
        automation_write = automation_write_requires_confirmation(name, arguments)
        structured_write = (is_native_action_proposal(name, arguments, [])
                            if self.require_native_write_approval else False)
        explicit_confirmation = needs_confirmation(arguments)
        if not (explicit_confirmation or automation_write or structured_write):
            return
        effect = action_effect_class(name, arguments,
                   write=(automation_write or structured_write or explicit_confirmation))
        self._decision = asyncio.get_running_loop().create_future()
        self.pending = {
            "id": str(uuid.uuid4()), **self.current,
            "approval_kind": ("automation_write" if automation_write
                              else "native_confirmation"),
            "effect_class": effect,
            "preview": action_preview(name, arguments, effect),
            "review_note": (
                "A native rule can be saved and active even when it is "
                "scheduled to repeat or has the wrong on/off effect. "
                "Check the exact date, target, polarity and recurrence."
                if automation_write else None
            ),
        }
        try:
            approved = await self._decision
            if not approved:
                raise MCPError("User declined this operation; do not retry it")
        finally:
            self.pending = None
            self._decision = None
