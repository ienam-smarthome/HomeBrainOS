"""Per-request progress and explicit confirmation for upstream confirm flags."""
from __future__ import annotations

import asyncio
import copy
import json
import uuid

from mcp import MCPError, redact
from action_intent_guard import automation_write_requires_confirmation


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


class Interaction:
    def __init__(self):
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
        if not (needs_confirmation(arguments) or automation_write):
            return
        self._decision = asyncio.get_running_loop().create_future()
        self.pending = {
            "id": str(uuid.uuid4()), **self.current,
            "approval_kind": ("automation_write" if automation_write
                              else "native_confirmation"),
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
