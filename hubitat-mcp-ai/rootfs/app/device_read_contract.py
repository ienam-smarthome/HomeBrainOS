from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_IDENTITY_FIELDS = ("id", "name", "label", "room")
_DETAIL_ONLY_FIELDS = frozenset({"capabilities", "attributes", "commands"})

LIVE_CONTEXT_RESOURCE_URI = "hubitat://context"
LIVE_CONTEXT_ATTRIBUTES = frozenset(
    {
        "switch",
        "level",
        "motion",
        "contact",
        "presence",
        "lock",
        "temperature",
        "humidity",
        "illuminance",
        "battery",
        "power",
        "energy",
        "thermostatMode",
        "thermostatOperatingState",
        "heatingSetpoint",
        "coolingSetpoint",
        "speed",
        "position",
        "valve",
        "water",
        "smoke",
    }
)


@dataclass(frozen=True, slots=True)
class DeviceReadPlan:
    """One explicit ``hub_list_devices`` projection contract.

    Hubitat MCP exposes live state differently in its two result modes:

    * summary mode emits compact ``currentStates``;
    * detailed mode emits reported live state as ``attributes``.

    Requesting capabilities or commands promotes the upstream server to detailed
    mode. Keeping that rule here prevents callers from constructing mixed
    projections such as ``capabilities + currentStates`` and then mistaking an
    omitted state field for proof that every device is inactive.
    """

    detailed: bool
    fields: tuple[str, ...]
    state_field: str | None

    def arguments(
        self,
        *,
        limit: int,
        offset: int = 0,
        capability_filter: str | None = None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {
            "detailed": self.detailed,
            "fields": list(self.fields),
            "limit": int(limit),
            "offset": int(offset),
        }
        if capability_filter:
            args["capabilityFilter"] = str(capability_filter)
        return args

    def has_state_container(self, device: dict[str, Any]) -> bool:
        """Return whether a projected record contains the promised state field.

        The field may legitimately contain an empty list/dict when the device has
        never reported state. A completely missing field means the response shape
        is not the contract this read plan requested.
        """

        return self.state_field is None or self.state_field in device


def device_read_plan(
    *,
    include_states: bool,
    include_capabilities: bool = False,
    include_commands: bool = False,
) -> DeviceReadPlan:
    """Build the correct field projection for the Hubitat MCP list contract."""

    detailed = bool(include_capabilities or include_commands)
    fields = list(_IDENTITY_FIELDS)
    if include_capabilities:
        fields.append("capabilities")
    state_field: str | None = None
    if include_states:
        state_field = "attributes" if detailed else "currentStates"
        fields.append(state_field)
    if include_commands:
        fields.append("commands")
    return DeviceReadPlan(
        detailed=detailed,
        fields=tuple(fields),
        state_field=state_field,
    )


def normalize_hub_list_devices_arguments(
    name: str,
    arguments: dict[str, Any],
) -> str | None:
    """Normalize a projected device-list request to the upstream wire contract.

    This is deliberately applied at the MCP boundary rather than in prompt or
    intent routing, so every caller gets the same protocol semantics. The
    upstream implementation auto-promotes projections containing capabilities,
    attributes, or commands into detailed mode. Detailed mode never emits the
    summary-only ``currentStates`` field, so a mixed projection must use
    ``attributes`` for state instead.

    The argument object is normalized in place so evidence records describe the
    actual request sent to Hubitat. The return value is the state field expected
    in the response, or ``None`` when the projection did not request state.
    """

    if name != "hub_read_devices" or arguments.get("tool") != "hub_list_devices":
        return None
    inner = arguments.get("args")
    if not isinstance(inner, dict):
        return None
    fields = inner.get("fields")
    if not isinstance(fields, list) or not fields:
        return None

    field_names = [str(field) for field in fields]
    detailed = bool(inner.get("detailed")) or any(
        field in _DETAIL_ONLY_FIELDS for field in field_names
    )
    state_requested = "currentStates" in field_names or "attributes" in field_names
    if not state_requested:
        return None

    expected = "attributes" if detailed else "currentStates"
    opposite = "currentStates" if expected == "attributes" else "attributes"
    normalized: list[str] = []
    for field in field_names:
        candidate = expected if field == opposite else field
        if candidate not in normalized:
            normalized.append(candidate)
    if expected not in normalized:
        normalized.append(expected)
    inner["fields"] = normalized
    if detailed:
        inner["detailed"] = True
    return expected


def projected_state_shape_is_usable(
    devices: list[dict[str, Any]],
    state_field: str | None,
) -> bool:
    """Check that a non-empty projected result actually carries state data.

    A missing state key on every returned record is a projection-contract
    failure, not evidence that all devices are inactive. Empty containers are
    valid; key presence is what distinguishes an empty state from an omitted
    field.
    """

    if state_field is None or not devices:
        return True
    return any(state_field in device for device in devices)


def live_context_is_complete(value: Any) -> bool:
    """Return whether ``hubitat://context`` can support exhaustive live claims.

    The upstream resource deliberately reports truncation, incomplete identity
    coverage, and per-device metadata/state failures in-band. HomeBrain must not
    turn any of those recoverable conditions into a confident whole-home answer;
    callers fall back to the established detailed inventory instead.
    """

    if not isinstance(value, dict):
        return False
    devices = value.get("devices")
    if not isinstance(devices, list) or not all(isinstance(item, dict) for item in devices):
        return False
    if value.get("truncated") is True or value.get("idsComplete") is False:
        return False
    if value.get("partial") is True:
        return False
    total = value.get("totalDevices")
    if total is not None:
        try:
            if int(total) != len(devices):
                return False
        except (TypeError, ValueError):
            return False
    return True


def live_context_devices(value: Any) -> list[dict[str, Any]]:
    """Normalize the compact context resource into HomeBrain's device shape.

    ``hubitat://context`` calls its compact state map ``attributes``. Convert that
    map to ``currentStates`` so a later merge with the richer metadata manifest
    keeps the manifest's typed/unit-bearing ``attributes`` list while live values
    still win in ``device_attributes``' merge order.
    """

    if not live_context_is_complete(value):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value.get("devices") or []:
        device = dict(item)
        states = device.pop("attributes", {})
        if isinstance(states, dict):
            device["currentStates"] = dict(states)
        normalized.append(device)
    return normalized


__all__ = [
    "DeviceReadPlan",
    "LIVE_CONTEXT_ATTRIBUTES",
    "LIVE_CONTEXT_RESOURCE_URI",
    "device_read_plan",
    "live_context_devices",
    "live_context_is_complete",
    "normalize_hub_list_devices_arguments",
    "projected_state_shape_is_usable",
]
