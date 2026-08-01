"""Local MCP tool schema definitions used by the UnifiedMCPAgent orchestrator.

Every function here is a pure builder for one deterministic, locally-handled
MCP tool schema (name, description, JSON schema, annotations). None of them
touch orchestrator state -- they exist so mcp_agent_orchestrator.py doesn't
have to carry ~240 lines of static schema literals inline. See
docs/ARCHITECTURE.md for how this fits into the request-handling pipeline.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from mcp_client import MCPTool

LOCAL_FILTER_TOOL = "homebrain_filter_devices"
LOCAL_QUERY_TOOL = "homebrain_query_devices"
LOCAL_ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
LOCAL_ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
LOCAL_ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"
LOCAL_HOME_SNAPSHOT_TOOL = "homebrain_home_snapshot"
LOCAL_CONTROL_TOOL = "homebrain_control_devices"
LOCAL_HUB_INFO_TOOL = "homebrain_hub_info_snapshot"
LOCAL_WEATHER_TOOL = "homebrain_weather_snapshot"

EVIDENCE_KINDS = {
    LOCAL_FILTER_TOOL: "deterministic_attribute_filter",
    LOCAL_QUERY_TOOL: "deterministic_attribute_query",
    LOCAL_ACTIVE_LIGHTS_TOOL: "deterministic_active_lights",
    LOCAL_ACTIVE_ROOMS_TOOL: "deterministic_active_rooms",
    LOCAL_ACTIVE_SWITCHES_TOOL: "deterministic_active_switches",
    LOCAL_HOME_SNAPSHOT_TOOL: "deterministic_home_snapshot",
    LOCAL_CONTROL_TOOL: "deterministic_device_control",
    LOCAL_HUB_INFO_TOOL: "authoritative_hub_info_snapshot",
    LOCAL_WEATHER_TOOL: "authoritative_weather_snapshot",
}


class ToolEffect(str, Enum):
    """Authoritative effect classification for one structured tool call."""

    READ = "read"
    ROUTINE_WRITE = "routine_write"
    SENSITIVE_WRITE = "sensitive_write"
    DESTRUCTIVE_WRITE = "destructive_write"

    @property
    def mutates(self) -> bool:
        return self is not ToolEffect.READ

    @property
    def requires_confirmation(self) -> bool:
        return self in {
            ToolEffect.SENSITIVE_WRITE,
            ToolEffect.DESTRUCTIVE_WRITE,
        }


_READ_GATEWAYS = {
    "hub_get_info",
    "hub_search_tools",
}
_DESTRUCTIVE_GATEWAYS = {"hub_manage_destructive_ops"}
_SENSITIVE_GATEWAYS = {"hub_update_firmware"}
_ROUTINE_DEVICE_COMMANDS = {
    "off", "on", "ping", "refresh", "set_color", "set_color_temperature",
    "set_level", "toggle", "update_check",
}
_SENSITIVE_DEVICE_COMMANDS = {
    "close", "lock", "open", "unlock",
}
_DESTRUCTIVE_ACTIONS = {
    "delete", "factory_reset", "remove", "replace", "reset_database", "swap",
}
_READ_ACTION_PREFIXES = (
    "check_", "find_", "get_", "list_", "read_", "search_", "status_",
)
_SENSITIVE_ACTION_PREFIXES = (
    "create_", "disable_", "enable_", "pause_", "reboot_", "restart_",
    "resume_", "set_", "shutdown_", "start_", "stop_", "update_",
)


def _normalized_operation(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")


def _structured_operations(arguments: dict[str, Any]) -> list[str]:
    operations: list[str] = []
    for key in ("tool", "operation", "action", "command"):
        value = _normalized_operation(arguments.get(key))
        if value:
            operations.append(value.removeprefix("hub_"))
    nested = arguments.get("args")
    if isinstance(nested, dict):
        for key in ("tool", "operation", "action", "command"):
            value = _normalized_operation(nested.get(key))
            if value:
                operations.append(value.removeprefix("hub_"))
    return operations


def _operation_effect(operations: list[str]) -> ToolEffect | None:
    for operation in operations:
        tokens = set(operation.split("_"))
        if tokens & _DESTRUCTIVE_ACTIONS:
            return ToolEffect.DESTRUCTIVE_WRITE
    for operation in operations:
        if operation in _SENSITIVE_DEVICE_COMMANDS:
            return ToolEffect.SENSITIVE_WRITE
        if operation in _ROUTINE_DEVICE_COMMANDS:
            return ToolEffect.ROUTINE_WRITE
    for operation in operations:
        if operation.startswith(_SENSITIVE_ACTION_PREFIXES):
            return ToolEffect.SENSITIVE_WRITE
    for operation in operations:
        if operation.startswith(_READ_ACTION_PREFIXES):
            return ToolEffect.READ
    return None


def _is_rule_schema_probe(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Recognise the upstream hub_set_rule no-confirm schema contract."""

    if tool_name != "hub_manage_rule_machine":
        return False
    if _normalized_operation(arguments.get("tool")) != "hub_set_rule":
        return False
    nested = arguments.get("args")
    if not isinstance(nested, dict):
        return False
    operation = _normalized_operation(nested.get("operation"))
    payload = nested.get("args")
    schema_only = payload is None or payload == "" or payload == {} or payload == []
    return (
        bool(operation)
        and nested.get("confirm") is not True
        and schema_only
    )


def classify_tool_effect(
    tool: MCPTool | None,
    arguments: dict[str, Any] | None = None,
) -> ToolEffect:
    """Classify an actual structured call without inspecting the user prompt.

    Unknown management calls fail closed as sensitive writes. Known structured
    sub-operations take precedence over broad gateway annotations so read and
    routine calls are not over-classified.
    """

    if tool is None:
        return ToolEffect.SENSITIVE_WRITE
    arguments = arguments if isinstance(arguments, dict) else {}
    annotations = tool.annotations or {}
    name = _normalized_operation(tool.name)

    if name in _DESTRUCTIVE_GATEWAYS:
        return ToolEffect.DESTRUCTIVE_WRITE
    if name in _SENSITIVE_GATEWAYS:
        return ToolEffect.SENSITIVE_WRITE
    if name == LOCAL_CONTROL_TOOL:
        return ToolEffect.ROUTINE_WRITE
    if name.startswith("homebrain_"):
        return ToolEffect.READ
    if name.startswith("hub_read_") or name in _READ_GATEWAYS:
        return ToolEffect.READ

    if _is_rule_schema_probe(name, arguments):
        return ToolEffect.READ

    operation_effect = _operation_effect(_structured_operations(arguments))
    if name.startswith("hub_manage_"):
        if operation_effect is not None:
            return operation_effect
        if annotations.get("destructiveHint") is True:
            return ToolEffect.DESTRUCTIVE_WRITE
        return ToolEffect.SENSITIVE_WRITE

    explicit_effect = str(annotations.get("effect") or "").strip().casefold()
    if explicit_effect in ToolEffect._value2member_map_:
        return ToolEffect(explicit_effect)
    danger = str(annotations.get("danger") or "").strip().casefold()
    if danger == "destructive":
        return ToolEffect.DESTRUCTIVE_WRITE
    if danger == "sensitive":
        return ToolEffect.SENSITIVE_WRITE
    if danger == "routine":
        return ToolEffect.ROUTINE_WRITE
    if annotations.get("destructiveHint") is True:
        return ToolEffect.DESTRUCTIVE_WRITE
    if annotations.get("readOnlyHint") is True or annotations.get("mutates") is False:
        return ToolEffect.READ
    if annotations.get("mutates") is True:
        return ToolEffect.SENSITIVE_WRITE
    return operation_effect or ToolEffect.SENSITIVE_WRITE


def device_filter_tool() -> MCPTool:
    return MCPTool(
        LOCAL_FILTER_TOOL,
        (
            "Fetch all live Hubitat devices and return only devices whose "
            "attribute satisfies a comparison. Use this for exhaustive lists, "
            "thresholds, counts, or comparisons instead of scanning the device "
            "manifest yourself."
        ),
        {
            "type": "object",
            "properties": {
                "attribute": {
                    "type": "string",
                    "description": "Hubitat attribute name, for example battery, temperature, humidity, power, switch, or motion.",
                },
                "operator": {
                    "type": "string",
                    "enum": [
                        "eq", "ne", "lt", "lte", "gt", "gte",
                        "contains", "exists", "not_exists",
                    ],
                },
                "value": {
                    "description": "Comparison value; omit only for exists/not_exists.",
                },
            },
            "required": ["attribute", "operator"],
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )


def device_query_tool() -> MCPTool:
    return MCPTool(
        LOCAL_QUERY_TOOL,
        (
            "Query all live Hubitat devices and compute a numeric aggregate before "
            "answering. Use maximum/minimum for highest or lowest, top/sort for "
            "rankings, and count for totals. Set group_by=room when the user asks "
            "which room, and device_kind=socket for socket or outlet questions."
        ),
        {
            "type": "object",
            "properties": {
                "attribute": {
                    "type": "string",
                    "description": "Numeric attribute such as power, temperature, humidity, or battery.",
                },
                "operation": {
                    "type": "string",
                    "enum": ["maximum", "minimum", "top", "sort", "count"],
                },
                "device_kind": {
                    "type": "string",
                    "enum": ["any", "light", "switch", "socket", "sensor"],
                    "default": "any",
                },
                "group_by": {
                    "type": "string",
                    "enum": ["none", "room"],
                    "default": "none",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                },
            },
            "required": ["attribute", "operation"],
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )


def weather_snapshot_tool() -> MCPTool:
    return MCPTool(
        LOCAL_WEATHER_TOOL,
        (
            "Read all current attributes from the Hubitat weather device. "
            "Use this for current-weather questions and when locating the "
            "weather device. Do not substitute ordinary indoor sensors."
        ),
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )


def active_rooms_tool() -> MCPTool:
    return MCPTool(
        LOCAL_ACTIVE_ROOMS_TOOL,
        (
            "Fetch all live Hubitat devices and deterministically return rooms "
            "that have motion=active or at least one light with switch=on. Use "
            "this whenever the user asks which rooms are active."
        ),
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )


def active_lights_tool() -> MCPTool:
    return MCPTool(
        LOCAL_ACTIVE_LIGHTS_TOOL,
        (
            "Fetch all live Hubitat devices and deterministically return every "
            "light or bulb whose switch state is on. Use this whenever the user "
            "asks which lights are on."
        ),
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )


def active_switches_tool() -> MCPTool:
    return MCPTool(
        LOCAL_ACTIVE_SWITCHES_TOOL,
        (
            "Fetch all live Hubitat devices and deterministically return devices "
            "with switch=on while excluding lights and bulbs. Use this whenever "
            "the user asks which switches are on."
        ),
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )


def home_snapshot_tool() -> MCPTool:
    return MCPTool(
        LOCAL_HOME_SNAPSHOT_TOOL,
        (
            "Fetch one live Hubitat device snapshot and deterministically summarize "
            "the whole home: presence, motion, active rooms, lights and non-light "
            "switches on, open contacts, unlocked locks, low batteries, and health "
            "alerts. Use this for broad questions such as what is happening at home."
        ),
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )


def control_devices_tool() -> MCPTool:
    return MCPTool(
        LOCAL_CONTROL_TOOL,
        (
            "Turn one or more Hubitat lights or switches on, off, or toggle them. "
            "Resolve targets deterministically from either an exact room or one or "
            "more device labels, then execute every matched command concurrently. "
            "Use this for routine light and switch control instead of making "
            "individual hub_manage_devices calls."
        ),
        {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Exact Hubitat room name. Selects every matching device_kind in that room.",
                },
                "device_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "One or more exact Hubitat device labels. Do not combine with room.",
                },
                "device_kind": {
                    "type": "string",
                    "enum": ["auto", "light", "switch"],
                    "description": (
                        "Use light for lights, switch for non-light switches, "
                        "or auto when a named target omits its device kind."
                    ),
                },
                "command": {
                    "type": "string",
                    "enum": ["on", "off", "toggle"],
                },
            },
            "required": ["device_kind", "command"],
            "oneOf": [
                {"required": ["room"]},
                {"required": ["device_names"]},
            ],
            "additionalProperties": False,
        },
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "mutates": True,
            "danger": "routine",
            "effect": ToolEffect.ROUTINE_WRITE.value,
        },
    )


def hub_info_tool() -> MCPTool:
    return MCPTool(
        LOCAL_HUB_INFO_TOOL,
        (
            "Refresh and read the authoritative Hub Information Driver device. "
            "Use this for Hubitat firmware availability, installed firmware, "
            "CPU, memory, temperature, uptime, database size, hub health, or "
            "general hub-information questions. This does not install firmware."
        ),
        {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["firmware", "resources", "full"],
                    "description": (
                        "firmware runs Update Check; resources refreshes telemetry; "
                        "full performs both before reading the Hub Info attributes."
                    ),
                },
            },
            "required": ["scope"],
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )
