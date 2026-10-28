"""Small, fixed source READ contracts for model-facing preflight repair.

These are *suggestions*, not generated tool calls or authorisations.
All real calls still go through the live manifest, tool schemas, typed IDs
and read-only host guard.
"""
from __future__ import annotations
from typing import Any, Mapping, Sequence
from evidence_gateway_contract import missing_required_read_fields

def read_contract_feedback(
    gateway: str, arguments: Mapping[str, Any],
    verified_typed: Mapping[str, set[str]],
) -> dict[str, Any] | None:
    if not gateway.startswith("hub_read_"):
        return None
    op = arguments.get("tool")
    if op not in ("hub_get_source", "hub_get_app_config", "hub_get_device"):
        return None
    fields = missing_required_read_fields(gateway, dict(arguments))
    if not fields:
        return None
    allowed = {kind: sorted(str(x) for x in verified_typed.get(kind, set())
                            if str(x).isdecimal())[:12]
               for kind in ("app", "driver", "device")}
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
    elif op == "hub_get_app_config":
        details["required_shape"] = {
            "tool": op, "args": {"appId": "source-attested app ID"}}
        details["verified_id_choices"] = {"app": allowed["app"]}
    else:
        details["required_shape"] = {
            "tool": op, "args": {"deviceId": "verified device ID"}}
        details["verified_id_choices"] = {"device": allowed["device"]}
    return details


__all__ = ["read_contract_feedback"]
