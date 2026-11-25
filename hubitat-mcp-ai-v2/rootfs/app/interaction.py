"""Per-request progress and explicit confirmation for upstream confirm flags."""
from __future__ import annotations

import asyncio
import copy
import json
import uuid

from mcp import MCPError, redact
from action_intent_guard import automation_write_requires_confirmation
from action_proposal_review import is_native_action_proposal
from native_action_contract import verified_device_details, numeric_minutes, timing_kind
from routine_approval_policy import (
    source_verified_auto_approval_class, matches_original_native_write,
    batch_light_authorization,
)


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


def action_preview(name: str, arguments: dict, effect: str, *, verified_devices: dict | None = None) -> dict:
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
    # Show safe numeric string or NUMBER parameters verbatim, never
    # modify the original native proposal or approval decision.
    params = safe.get("parameters", safe.get("params")) if isinstance(safe, dict) else None
    numeric = None
    if (isinstance(params, list) and 0 < len(params) <= 5
            and all(numeric_minutes(value) is not None for value in params)):
        fields["parameters"] = ", ".join(numeric_minutes(value) for value in params)[:80]
        if len(params) == 1:
            numeric = numeric_minutes(params[0])
    # Only an ID-matched original native device-detail result supplies
    # the display name. The label NEVER changes target or native tool args.
    original_id = fields.get("device")
    verified = (verified_devices or {}).get(original_id) if original_id else None
    if isinstance(verified, dict) and verified.get("label"):
        fields["device_id"] = original_id
        fields["device"] = verified["label"]
        proposed = safe.get("command") if isinstance(safe, dict) else None
        if (isinstance(proposed, str)
                and proposed in verified.get("commands", set())
                and numeric is not None):
            semantics = timing_kind(proposed)
            if semantics == "delay":
                fields["timing"] = f"After {numeric} minutes (delay, not duration)"
            elif semantics == "duration":
                fields["timing"] = f"For {numeric} minutes (duration, not delay)"
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
    def __init__(self, *, require_native_write_approval: bool = False,
                 auto_approve_lights: bool = False,
                 trusted_safe_switch_ids: frozenset[str] = frozenset(),
                 auto_approve_internet_block: bool = False):
        self.auto_approve_internet_block = auto_approve_internet_block is True
        self.require_native_write_approval = require_native_write_approval
        self.auto_approve_lights = auto_approve_lights is True
        self.trusted_safe_switch_ids = frozenset(trusted_safe_switch_ids)
        self._routine_proof: dict | None = None
        self.routine_auto_approval_used = False
        self.routine_auto_approval_class: str | None = None
        self.current = None
        self.pending = None
        self._decision = None
        self._verified_devices: dict[str, dict] = {}
        self._cancelled = False
        self.native_write_submission_started = False
        self.phase: dict = {"kind": "queued"}

    def set_phase(self, kind: str, *, detail: str = "") -> None:
        """Safe bounded progress, not simulated device evidence."""
        if not self._cancelled:
            self.phase = {"kind": kind, "detail": detail[:90]}

    def invalidate(self) -> None:
        """Superseded requests lose all native approval authority immediately."""
        self._cancelled = True
        self._routine_proof = None  # Request cannot reuse original Ask authority.
        self.phase = {"kind": "cancelled"}
        if self._decision is not None and not self._decision.done():
            self._decision.cancel()
        self.pending = None

    def note_native_write_submission(self) -> None:
        """Marks an uncertain-write boundary, not acceptance or outcome."""
        if self._cancelled:
            raise MCPError("This request was superseded before native dispatch")
        self.native_write_submission_started = True

    def register_current_native_device_details(self, receipts: list[dict]) -> None:
        """Source-only display registry for this particular Ask/approval."""
        self._verified_devices = verified_device_details(receipts)

    def offer_current_ask_routine_authorization(
        self, candidate: dict | None, receipts: list[dict],
    ) -> bool:
        """Single-use, exact-native-writer authorization for this current Ask.

        The agent must first verify the current original request against its
        model-selected native tool and fresh ORIGINAL native MCP receipts.
        This does not create, select, submit, or rewrite a tool. It cannot be
        used by another request or after any native write submission.
        """
        self._routine_proof = None
        if (self._cancelled or self.native_write_submission_started
                or not self.require_native_write_approval):
            return False
        allowed_class = source_verified_auto_approval_class(
            candidate, receipts, auto_lights=self.auto_approve_lights,
            safe_switch_ids=self.trusted_safe_switch_ids,
        )
        if allowed_class is None:
            return False
        self._routine_proof = {
            "candidate": copy.deepcopy(candidate),
            "class": allowed_class,
        }
        return True

    def offer_batch_routine_authorization(self, args: dict, candidates: list[dict],
                                          receipts: list[dict]) -> bool:
        """Single-use authorization for one structured on/off batch whose every target passed
        the single-device policy on fresh original reads. Bound to the exact arguments."""
        self._routine_proof = None
        if (self._cancelled or self.native_write_submission_started
                or not self.require_native_write_approval or not self.auto_approve_lights):
            return False
        if not batch_light_authorization(candidates, receipts,
                                         safe_switch_ids=self.trusted_safe_switch_ids):
            return False
        self._routine_proof = {"batch_args": copy.deepcopy(args), "class": "verified_light_batch"}
        return True

    def offer_internet_block_authorization(self, args: dict, candidate: dict | None) -> bool:
        """Single-use authorization for one verified per-device block/allow command, bound to exact args."""
        self._routine_proof = None
        if (candidate is None or self._cancelled or self.native_write_submission_started
                or not self.require_native_write_approval or not self.auto_approve_internet_block):
            return False
        self._routine_proof = {"internet_args": copy.deepcopy(args), "class": "verified_internet_block"}
        return True

    def status(self) -> dict:
        return {"current": self.current, "pending": self.pending,
                "phase": self.phase, "cancelled": self._cancelled}

    def decide(self, approval_id: str, approved: bool) -> None:
        if (self._cancelled or not self.pending or self.pending["id"] != approval_id
                or self._decision is None or self._decision.done()):
            raise ValueError("This confirmation is no longer pending")
        self._decision.set_result(approved)

    async def before_call(self, name: str, arguments: dict, explanation: str) -> None:
        if self._cancelled:
            raise MCPError("This request was superseded; no native action authorised")
        self.current = {
            "name": name, "arguments": redact(copy.deepcopy(arguments)),
            "explanation": redact(explanation),
        }
        automation_write = automation_write_requires_confirmation(name, arguments)
        structured_write = (is_native_action_proposal(name, arguments, [])
                            if self.require_native_write_approval else False)
        explicit_confirmation = needs_confirmation(arguments)
        # Consume the proof on the VERY NEXT native call, whether or not its
        # name/args match. Extra/changed writes can never inherit permission.
        proof = self._routine_proof
        self._routine_proof = None
        if (structured_write and not automation_write
                and not explicit_confirmation
                and not self.routine_auto_approval_used
                and isinstance(proof, dict)
                and ((proof.get("batch_args") is not None
                      and name == "hub_call_device_command"
                      and proof["batch_args"] == arguments)
                     or (proof.get("internet_args") is not None
                         and name == "hub_call_device_command"
                         and proof["internet_args"] == arguments)
                     or (proof.get("candidate") is not None
                         and matches_original_native_write(
                             proof["candidate"], name, arguments)))):
            self.routine_auto_approval_used = True
            self.routine_auto_approval_class = proof["class"]
            self.set_phase(
                "approved",
                detail="Original Ask authorised verified routine native command",
            )
            return
        if not (explicit_confirmation or automation_write or structured_write):
            return
        effect = action_effect_class(name, arguments,
                   write=(automation_write or structured_write or explicit_confirmation))
        self._decision = asyncio.get_running_loop().create_future()
        self.set_phase("awaiting_approval", detail="Real native write pending your decision")
        self.pending = {
            "id": str(uuid.uuid4()), **self.current,
            "approval_kind": ("automation_write" if automation_write
                              else "native_confirmation"),
            "effect_class": effect,
            "preview": action_preview(
                name, arguments, effect,
                verified_devices=self._verified_devices
            ),
            "review_note": (
                "A native rule can be saved and active even when it is "
                "scheduled to repeat or has the wrong on/off effect. "
                "Check the exact date, target, polarity and recurrence."
                if automation_write else None
            ),
        }
        try:
            approved = await self._decision
            if self._cancelled:
                raise MCPError("This request was superseded; no native action authorised")
            if not approved:
                raise MCPError("User declined this operation; do not retry it")
            self.set_phase("approved", detail="Native action approved; awaiting dispatch")
        finally:
            self.pending = None
            self._decision = None
