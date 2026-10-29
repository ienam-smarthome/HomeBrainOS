"""Small, fixed source READ contracts for model-facing preflight repair.

These are *suggestions*, not generated tool calls or authorisations.
All real calls still go through the live manifest, tool schemas, typed IDs
and read-only host guard.
"""
from __future__ import annotations
from typing import Any, Mapping, Sequence
from evidence_gateway_contract import missing_required_read_fields

def advertised_operation_contracts(operations: Sequence[str]) -> str:
    """Only advertise concrete requirements for operations in a live enum.

    This describes the already-authorised gateway shape; it never adds
    operations, expands the host schema or supplies device identities.
    """
    known = set(operations)
    notes = []
    if "hub_get_device" in known:
        notes.append("hub_get_device: args.deviceId REQUIRED (verified numeric device ID); optional args.mode")
    if "hub_list_device_events" in known:
        notes.append("hub_list_device_events: args.deviceId for scoped device history")
    if "hub_get_app_config" in known:
        notes.append("hub_get_app_config: args.appId REQUIRED (verified app ID)")
    if "hub_get_source" in known:
        notes.append("hub_get_source: args.type and args.id BOTH REQUIRED; source ID must match type")
    return "; ".join(notes)


def read_contract_feedback(
    gateway: str, arguments: Mapping[str, Any],
    verified_typed: Mapping[str, set[str]],
    *, focus_ids: Sequence[str] = (),
) -> dict[str, Any] | None:
    if not gateway.startswith("hub_read_"):
        return None
    op = arguments.get("tool")
    if op not in ("hub_get_source", "hub_get_app_config",
                  "hub_get_device", "hub_list_device_events"):
        return None
    fields = missing_required_read_fields(gateway, dict(arguments))
    if op == "hub_list_device_events":
        inner = arguments.get("args", {})
        if not isinstance(inner, Mapping) or (
                inner.get("deviceId") is None and inner.get("appId") is None):
            fields = ["deviceId|appId"]
    if not fields:
        return None
    focus = sorted({str(x) for x in focus_ids
                    if str(x).isdecimal()
                    and str(x) in verified_typed.get("device", set())})
    # Do not obscure the actual verified target beneath the first 12 of
    # hundreds of hub-wide unrelated identity receipts.
    allowed = {kind: sorted(str(x) for x in verified_typed.get(kind, set())
                            if str(x).isdecimal())[:6]
               for kind in ("app", "driver", "device")}
    if focus:
        allowed["device"] = focus[:3] + [
            x for x in allowed["device"] if x not in focus][:3]
    details: dict[str, Any] = {
        "operation": op,
        "missing_required_fields": list(fields),
        "arguments_location": "args",
        "read_only": True,
        "host_execution_attempted": False,
        "schema_examples_are_not_authorisation": True,
    }
    if op == "hub_get_source":
        details["required_shape"] = {
            "tool": "hub_get_source",
            "args": {"type": "app|driver", "id": "source-attested numeric ID"},
        }
        details["verified_id_choices"] = {
            "app": allowed["app"], "driver": allowed["driver"],
        }
        details["guidance"] = (
            "For an independently verified calling app choose type='app' "
            "and id equal to that app's verified ID; for driver code choose "
            "type='driver' and a separately attested driver ID. "
            "App IDs cannot authorise driver-source reads. "
            "Never guess or reuse a deviceId as a source id.")
    elif op == "hub_list_device_events":
        details["required_shape"] = {
            "tool": op, "args": {"deviceId": "verified device ID"}}
        details["verified_id_choices"] = {"device": allowed["device"]}
        details["guidance"] = (
            "For the independently verified target device, explicitly "
            "include deviceId; this is only an example, not an executed "
            "operation. Unscoped events cover a different source.")
    elif op == "hub_get_app_config":
        details["required_shape"] = {
            "tool": op, "args": {"appId": "source-attested app ID"}}
        details["verified_id_choices"] = {"app": allowed["app"]}
    else:
        concrete = (focus[0] if len(focus) == 1
                    else "verified device ID")
        details["required_shape"] = {
            "tool": op, "args": {"deviceId": concrete}}
        details["verified_id_choices"] = {"device": allowed["device"]}
        if len(focus) == 1:
            details["verified_focus_device_id"] = concrete
            details["guidance"] = (
                "The uniquely verified question subject is deviceId="
                + concrete + ". Include it inside args (not at the "
                "gateway top level). This is feedback, NOT an executed "
                "or automatically repaired read.")
    return details


__all__ = ["read_contract_feedback", "advertised_operation_contracts"]
