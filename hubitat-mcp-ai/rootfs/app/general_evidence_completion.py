"""Source-class completeness for opt-in semantic MCP investigations.

A source-class check only means a relevant read was attempted successfully.
It is NEVER proof of a particular event, historical trigger, online status,
time coverage, command delivery, or action outcome. The class inventory is
based on *executed receipts*, not model narration or tool discovery results.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from historical_command_source_contract import mixed_command_events
from method_command_source_contract import typed_method_command_records

EVIDENCE_KINDS = frozenset({
    "device_state",
    "device_history",
    "device_logs",
    "app_config",
    "app_logs",
    "room_inventory",
    "native_rules",
    "scheduled_jobs",
    "performance_stats",
    "tool_guide",
    "command_history",
    "source_code",
})

_READ_OPERATIONS: dict[str, str] = {
    "hub_get_device": "device_state",
    "hub_list_device_events": "device_history",
    "homebrain_device_history": "device_history",
    "hub_get_room": "room_inventory",
    "hub_list_rooms": "room_inventory",
    "hub_get_app_config": "app_config",
    "hub_get_rule": "native_rules",
    "hub_list_rules": "native_rules",
    "hub_get_jobs": "scheduled_jobs",
    "hub_get_performance_stats": "performance_stats",
    "hub_get_tool_guide": "tool_guide",
}

def _operation(receipt: dict[str, Any]) -> str:
    if receipt.get("sub_tool"):
        return str(receipt["sub_tool"])
    arguments = receipt.get("arguments")
    if isinstance(arguments, dict) and isinstance(arguments.get("tool"), str):
        return str(arguments["tool"])
    return str(receipt.get("tool") or "")


def _args(receipt: dict[str, Any]) -> dict[str, Any]:
    value = receipt.get("arguments")
    if not isinstance(value, dict):
        return {}
    # A malformed model envelope with nested args is not a valid evidence read.
    for _ in range(2):
        if isinstance(value.get("args"), dict):
            value = value["args"]
        else:
            break
    return value


def _kind(receipt: dict[str, Any]) -> str | None:
    op = _operation(receipt)
    raw = receipt.get("arguments")
    if (isinstance(raw, dict) and isinstance(raw.get("args"), dict)
            and isinstance(raw["args"].get("args"), dict)):
        return None  # malformed double-wrapped gateway call
    args = _args(receipt)
    if op in {"homebrain_read_groovy_source", "hub_get_source"}:
        details = receipt.get("details") or {}
        return "source_code" if isinstance(details, dict) and details.get("sourceRetrieved") is True else None
    if op == "hub_get_logs":
        if args.get("deviceId") or args.get("device_id"):
            return "device_logs"
        if args.get("appId") or args.get("app_id"):
            return "app_logs"
        # Whole-hub log reads cannot establish app/device-specific coverage.
        return None
    if op == "hub_list_device_events" and str(args.get("attribute") or "").casefold().startswith("command-"):
        return "command_history"
    if op == "hub_list_devices":
        # A basic list is identity navigation. Only a detailed, scoped
        # projection contains state and can count as a device-state read.
        if args.get("detailed") is True and args.get("labelFilter"):
            return "device_state"
        return None
    return _READ_OPERATIONS.get(op)


@dataclass(frozen=True)
class EvidenceCoverage:
    required: tuple[str, ...]
    checked: tuple[str, ...]
    missing: tuple[str, ...]

    @property
    def sources_checked(self) -> bool:
        return not self.missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "requiredSourceKinds": list(self.required),
            "checkedSourceKinds": list(self.checked),
            "missingSourceKinds": list(self.missing),
            "sourceKindsChecked": self.sources_checked,
            "note": (
                "Source-class checks do not establish that the requested "
                "historic event, cause, command, or state was verified."
            ),
        }

    def retry_instruction(self) -> str:
        return (
            "HOST SOURCE-COMPLETENESS CHECK (read-only): Some required "
            "investigative source classes were not checked in this turn. "
            + json.dumps(self.to_dict(), ensure_ascii=False)
            + "\nMake at most one focused read for each relevant missing "
              "source class if the installed MCP server exposes it and the "
              "read can be safely scoped. Discover the precise live sub-tool "
              "before using a gateway. Do not invent schemas. If missing "
              "evidence is unavailable, explain the limitation and finish "
              "with a partial investigation, not a fabricated conclusion. "
              "No mutation or tool-call confirmation is authorised."
        )


def assess_task_source_coverage(
    required: tuple[str, ...] | list[str],
    receipts: list[dict[str, Any]],
) -> EvidenceCoverage:
    """Check actual successful read receipts, preserving checked vs proven."""
    needs = tuple(dict.fromkeys(
        item for item in required if item in EVIDENCE_KINDS
    ))
    seen: set[str] = set()
    for row in receipts:
        if not isinstance(row, dict) or row.get("success") is not True:
            continue
        if row.get("mutates") is True or row.get("effect") not in (None, "read"):
            continue
        op = _operation(row)
        if op in {"hub_search_tools"}:
            continue
        kind = _kind(row)
        if kind:
            seen.add(kind)
        # A single unfiltered, target-scoped Hubitat device-event read can
        # return both switch events and real command-on/off records. This is
        # positive command-history evidence even though the request omitted
        # attribute=command-off. Do not count empty generic history pages,
        # malformed events or mere model narration as command source checks.
        if mixed_command_events(row):
            seen.add("command_history")
    # Other typed Hubitat method calls (setThermostatMode, setLevel,
    # setHeatingSetpoint, etc.) are also command history, even when no
    # command-off/command-on attribute filter was requested. Their trusted
    # deterministic wrapper must identify its exact queried label.
    # This proves a bounded command record exists, not historical completeness.
    if typed_method_command_records(receipts):
        seen.add("command_history")
    checked = tuple(kind for kind in needs if kind in seen)
    missing = tuple(kind for kind in needs if kind not in seen)
    return EvidenceCoverage(needs, checked, missing)


__all__ = ["EvidenceCoverage", "EVIDENCE_KINDS", "assess_task_source_coverage"]
