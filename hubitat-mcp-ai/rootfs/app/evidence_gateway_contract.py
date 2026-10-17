"""Structural read-only MCP gateway validation before hub execution.

Model-generated gateway payloads can accidentally contain duplicated envelopes
(e.g. args={tool:"hub_get_logs",args:{deviceId:...}}). Preserve the
user's device/time filters by normalizing *only identical read tool wrappers*.
Never apply this normalization to a mutating command.

For read endpoints with a defined required input, reject incomplete calls
locally instead of bothering the hub with calls that cannot yield evidence.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_READ_GATEWAYS = frozenset({
    "hub_read_devices", "hub_read_diagnostics", "hub_manage_logs",
    "hub_manage_devices", "hub_read_apps_code",
})
_READ_LEAVES = frozenset({
    "hub_get_device", "hub_get_device_attribute", "hub_list_devices",
    "hub_list_device_events", "hub_get_logs", "hub_get_jobs",
    "hub_get_performance_stats", "hub_get_metrics", "hub_get_app_config",
    "hub_get_source", "hub_list_apps",
})
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "hub_get_device_attribute": ("deviceId", "attribute"),
    "hub_get_device": ("deviceId",),
    "hub_get_app_config": ("appId",),
    "hub_get_source": ("id", "type"),
}


def normalize_gateway_read(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in _READ_GATEWAYS or not isinstance(arguments, dict):
        return arguments
    payload = deepcopy(arguments)
    leaf = payload.get("tool")
    if leaf not in _READ_LEAVES:
        return payload
    args = payload.get("args")
    for _ in range(3):
        if not isinstance(args, dict) or args.get("tool") != leaf:
            break
        nested = args.get("args")
        if not isinstance(nested, dict):
            break
        args = nested
    payload["args"] = args if isinstance(args, dict) else payload.get("args")
    return payload


def missing_required_read_fields(
    name: str, arguments: dict[str, Any]
) -> tuple[str, ...]:
    if name not in _READ_GATEWAYS or not isinstance(arguments, dict):
        return ()
    leaf = arguments.get("tool")
    if leaf not in _READ_LEAVES:
        return ()
    fields = _REQUIRED_FIELDS.get(str(leaf), ())
    payload = arguments.get("args")
    if not isinstance(payload, dict):
        payload = {}
    return tuple(
        field for field in fields
        if payload.get(field) is None
        or (isinstance(payload.get(field), str)
            and not payload[field].strip())
    )


__all__ = ["normalize_gateway_read", "missing_required_read_fields"]
