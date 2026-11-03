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
        # Health/transport diagnostics are live state too. Room-status queries
        # need these in the compact context or an offline sensor can be reduced
        # to its retained motion/presence value.
        "sensorStatus",
        "healthStatus",
        "mqttStatus",
        "lastMessage",
        "lastError",
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
        # Upstream accepts format/cursor, NOT detailed/offset.  Keep the
        # Python plan's detailed/offset concepts internally only.
        args: dict[str, Any] = {
            "format": "detailed" if self.detailed else "summary",
            "fields": list(self.fields),
            "limit": int(limit),
            "cursor": str(int(offset)),
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
    include_last_activity: bool = False,
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
    if include_last_activity:
        fields.append("lastActivity")
    return DeviceReadPlan(
        detailed=detailed,
        fields=tuple(fields),
        state_field=state_field,
    )


def normalize_hub_list_devices_arguments(
    name: str,
    arguments: dict[str, Any],
) -> str | None:
    """Translate internal projected reads to the upstream MCP wire contract.

    All `hub_list_devices` gateway calls must use `format` (summary/detailed)
    and `cursor` for paging. The upstream server rejects the legacy
    `detailed` and `offset` arguments as unknown BEFORE reading the hub.
    This normalization runs once at the MCP client boundary, preserving the
    same requested scope/label and making evidence reflect the sent request.
    """
    if name != "hub_read_devices" or arguments.get("tool") != "hub_list_devices":
        return None
    inner = arguments.get("args")
    if not isinstance(inner, dict):
        return None

    legacy_detailed = inner.pop("detailed", None)
    legacy_offset = inner.pop("offset", None)
    if legacy_offset is not None and "cursor" not in inner:
        inner["cursor"] = str(legacy_offset)

    fields = inner.get("fields")
    field_names = [str(field) for field in fields] if isinstance(fields, list) else []
    detail_projected = any(field in _DETAIL_ONLY_FIELDS for field in field_names)
    format_requested = inner.get("format")
    detailed = (
        format_requested == "detailed" or legacy_detailed is True
        or detail_projected
    )
    if detailed and format_requested in (None, "summary", "detailed"):
        inner["format"] = "detailed"
    elif legacy_detailed is False and format_requested is None:
        inner["format"] = "summary"

    if not field_names:
        return None
    state_requested = "currentStates" in field_names or "attributes" in field_names
    if not state_requested:
        return None

    # In detailed mode the native state container is attributes; in summary
    # mode it is currentStates. A missing response state remains unresolved,
    # not evidence that every device is switched off.
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
    return expected


def projected_state_shape_is_usable(
    devices: list[dict[str, Any]],
    state_field: str | None,
) -> bool:
    """Check that every projected record carries the promised state container.

    Empty state containers are valid. A missing state key on even one returned
    record means the projected response is structurally incomplete and cannot
    support an exhaustive live-state claim. Accepting a single well-shaped record
    would allow another malformed record to be silently interpreted as inactive.
    """

    if state_field is None or not devices:
        return True
    return all(state_field in device for device in devices)


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
