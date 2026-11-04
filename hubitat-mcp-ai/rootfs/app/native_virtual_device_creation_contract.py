"""Source-backed virtual-device creation tool boundary.

An MCP-managed built-in Virtual Switch is created by the direct upstream
hub_manage_virtual_device(action=create, deviceType=Virtual Switch) tool.
hub_manage_devices(tool=hub_create_device) is a different native driver-ID
contract and must never be fed a display driver type as deviceTypeId.

This guard validates *plans* before confirmation and on confirmation replay;
it NEVER performs a device write, creates a confirmation or fabricates a
driver ID from a name. The installed MCP tool catalog is the authority.
"""
from __future__ import annotations

import re
from typing import Any

_DIRECT_TOOL = "hub_manage_virtual_device"
_LEGACY_GATEWAY = "hub_manage_devices"
_LEGACY_CREATE = "hub_create_device"

# Exact built-in native types from upstream MCP virtual device contract.
_TYPES = (
    "Virtual Switch", "Virtual Button", "Virtual Contact Sensor",
    "Virtual Motion Sensor", "Virtual Presence", "Virtual Lock",
    "Virtual Temperature Sensor", "Virtual Humidity Sensor",
    "Virtual Dimmer", "Virtual RGBW Light", "Virtual Shade",
    "Virtual Garage Door Controller", "Virtual Leak Sensor",
    "Virtual Omni Sensor", "Virtual Fan Controller",
)
_TYPE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(_TYPES, key=len, reverse=True))
    + r")\b", re.I,
)
_POSITIVE_CREATE = re.compile(r"\b(?:create|add|provision|make)\b", re.I)
_NEGATIVE_CLAUSE = re.compile(
    r"^\s*(?:do\s+not|don't|never|without|no)\b", re.I,
)
_ID = re.compile(r"[1-9]\d{0,9}\Z")


def requested_virtual_device_type(question: str) -> str | None:
    """Recognise an affirmative built-in virtual-device create objective.

    Negative safety clauses ("do not create a rule or virtual device")
    never grant permission. Device reads and rule creation are not inferred
    as device creation just because the prompt mentions a virtual switch.
    """
    for clause in re.split(r"[.!?\n]+", str(question or "")):
        if _NEGATIVE_CLAUSE.match(clause) or not _POSITIVE_CREATE.search(clause):
            continue
        for match in _TYPE_PATTERN.finditer(clause):
            if _POSITIVE_CREATE.search(clause[:match.start()]):
                return next(t for t in _TYPES if t.casefold() == match.group(1).casefold())
    return None


def virtual_device_creation_error(
    tool_name: str, arguments: dict[str, Any] | Any, *,
    requested_type: str | None = None,
    server_generated_dni: bool = False,
) -> str | None:
    """Refuse schema confusion on either side of the human confirmation.

    A wrong legacy gateway with a nonnumeric type ID is invalid regardless
    of what the user asked. A confirmed virtual-device request cannot be
    silently swapped for a different tool, type, target or delete.
    """
    if not isinstance(arguments, dict):
        return "Virtual-device write arguments were malformed."
    if tool_name == _LEGACY_GATEWAY and arguments.get("tool") == _LEGACY_CREATE:
        inner = arguments.get("args")
        if not isinstance(inner, dict):
            return "Native device creation requires a typed argument object."
        driver_id = inner.get("deviceTypeId")
        if requested_type is not None or not (
            isinstance(driver_id, (str, int))
            and not isinstance(driver_id, bool)
            and _ID.fullmatch(str(driver_id))
        ):
            return (
                "Virtual device creation uses the separate installed "
                "hub_manage_virtual_device tool with action=create and "
                "deviceType (not hub_create_device/deviceTypeId). "
                "No device create has been queued or sent."
            )
    if tool_name != _DIRECT_TOOL:
        return None
    action = arguments.get("action")
    if requested_type is not None and action != "create":
        return "The requested virtual-device creation cannot be replaced by another action."
    if action != "create":
        return None
    driver = arguments.get("deviceType")
    custom = arguments.get("customDriver")
    if (driver is None) == (custom is None):
        return "Virtual device creation requires exactly one supported built-in type or custom driver."
    if requested_type is not None and (
        driver != requested_type or custom is not None
    ):
        return (
            f"The approved virtual-device type is {requested_type}; "
            "no different driver type can be substituted."
        )
    label = arguments.get("deviceLabel")
    if not isinstance(label, str) or not label.strip() or len(label) > 160:
        return "Virtual-device creation requires one nonempty bounded deviceLabel."
    if server_generated_dni and arguments.get("deviceNetworkId") not in (None, ""):
        return "A server-generated device network ID was requested; do not supply one."
    return None


def needs_server_generated_dni(prompt: str) -> bool:
    return bool(re.search(
        r"\b(?:server[- ]generated|auto[- ]generated|automatically generated)\b"
        r"[^.!?\n]{0,70}\b(?:device network id|dni)\b",
        str(prompt or ""), re.I,
    ))


__all__ = [
    "requested_virtual_device_type", "virtual_device_creation_error",
    "needs_server_generated_dni",
]
