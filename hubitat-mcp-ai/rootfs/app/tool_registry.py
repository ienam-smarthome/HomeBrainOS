"""Local MCP tool schema definitions used by the UnifiedMCPAgent orchestrator.

Every function here is a pure builder for one deterministic, locally-handled
MCP tool schema (name, description, JSON schema, annotations). None of them
touch orchestrator state -- they exist so mcp_agent_orchestrator.py doesn't
have to carry ~240 lines of static schema literals inline. See
docs/ARCHITECTURE.md for how this fits into the request-handling pipeline.
"""

from __future__ import annotations

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
        annotations={"readOnlyHint": True},
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
        annotations={"readOnlyHint": True},
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
        annotations={"readOnlyHint": True},
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
        annotations={"readOnlyHint": True},
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
        annotations={"readOnlyHint": True},
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
        annotations={"readOnlyHint": True},
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
        annotations={"readOnlyHint": True},
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
        annotations={"readOnlyHint": False, "destructiveHint": False, "mutates": True, "danger": "routine"},
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
        annotations={"readOnlyHint": True},
    )
