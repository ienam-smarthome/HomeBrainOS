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
LOCAL_RESOLVE_TOOL = "homebrain_resolve_device"
LOCAL_DEVICE_HISTORY_TOOL = "homebrain_device_history"
LOCAL_ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
LOCAL_ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
LOCAL_ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"
LOCAL_HOME_SNAPSHOT_TOOL = "homebrain_home_snapshot"
LOCAL_CONTROL_TOOL = "homebrain_control_devices"
LOCAL_HUB_INFO_TOOL = "homebrain_hub_info_snapshot"
LOCAL_WEATHER_TOOL = "homebrain_weather_snapshot"
HUB_UPDATE_FIRMWARE_TOOL = "hub_update_firmware"

EVIDENCE_KINDS = {
    LOCAL_FILTER_TOOL: "deterministic_attribute_filter",
    LOCAL_QUERY_TOOL: "deterministic_attribute_query",
    LOCAL_RESOLVE_TOOL: "deterministic_targeted_device_resolution",
    LOCAL_DEVICE_HISTORY_TOOL: "deterministic_device_event_history",
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
_SENSITIVE_GATEWAYS = {HUB_UPDATE_FIRMWARE_TOOL}
# hub_manage_virtual_device and hub_manage_mode are documented as *direct*
# tools by the connected Hubitat MCP server, not gateways -- they don't
# expose sub-tools, so an empty-args call to either isn't the harmless
# "list this gateway's sub-tools" schema-discovery convention every other
# hub_manage_* gateway supports. Excluding them from the schema-probe check
# means an empty-args call falls through to the normal hub_manage_
# classification path and fails closed to SENSITIVE_WRITE (requiring
# confirmation) instead of being waved through as a safe read.
_DIRECT_MANAGE_TOOLS = {"hub_manage_virtual_device", "hub_manage_mode"}
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
        # `_DESTRUCTIVE_ACTIONS` holds both single-word entries ("delete",
        # "remove") and two-word entries ("factory_reset",
        # "reset_database") -- splitting `operation` on "_" and
        # intersecting with the set only ever matches the single-word
        # ones (`{"factory", "reset"} & _DESTRUCTIVE_ACTIONS` is empty
        # even though "factory_reset" is a member of the set itself), so
        # the two multi-word entries could never match. Checking the
        # un-split, already-normalised operation string directly catches
        # those too, alongside the existing single-token check.
        tokens = set(operation.split("_"))
        if operation in _DESTRUCTIVE_ACTIONS or tokens & _DESTRUCTIVE_ACTIONS:
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


def _is_gateway_schema_probe(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Recognise the upstream no-argument gateway schema contract.

    hub_manage_virtual_device and hub_manage_mode are excluded: they are
    documented direct tools, not gateways, so an empty-args call to either
    is a real invocation attempt, not a harmless schema-discovery probe.
    """

    return (
        tool_name.startswith("hub_manage_")
        and tool_name not in _DIRECT_MANAGE_TOOLS
        and not arguments
    )


def _is_rule_capability_probe(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Recognise documented non-mutating hub_set_rule capability discovery."""

    if tool_name != "hub_manage_rule_machine":
        return False
    if _normalized_operation(arguments.get("tool")) != "hub_set_rule":
        return False
    payload = arguments.get("args")
    if not isinstance(payload, dict) or payload.get("confirm") is True:
        return False
    visible = {
        key: value
        for key, value in payload.items()
        if key not in {"bestPracticeKey"}
    }
    return visible in (
        {"addTrigger": {"discover": True}},
        {"addAction": {"discover": True}},
    )


def _rule_specs(
    payload: dict[str, Any],
    singular: str,
    plural: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return normalized shortcut specs without accepting malformed lists."""

    specs: list[dict[str, Any]] = []
    if singular in payload:
        value = payload.get(singular)
        if not isinstance(value, dict):
            return [], f"{singular} must be an object"
        specs.append(value)
    if plural in payload:
        value = payload.get(plural)
        if not isinstance(value, list) or not value:
            return [], f"{plural} must be a non-empty array"
        if any(not isinstance(item, dict) for item in value):
            return [], f"every {plural} item must be an object"
        specs.extend(value)
    return specs, None


def _rule_shortcut_error(payload: dict[str, Any]) -> str | None:
    """Validate stable upstream trigger/action shortcut invariants.

    The live discovery schema remains authoritative for the full capability
    catalog. These checks deliberately cover contract rules that must never be
    guessed: time-trigger shape, mapped switch actions, custom commands, and
    the ambiguous many-times/many-actions topology that caused a partial rule.
    """

    triggers, error = _rule_specs(payload, "addTrigger", "addTriggers")
    if error:
        return error
    actions, error = _rule_specs(payload, "addAction", "addActions")
    if error:
        return error

    for index, trigger in enumerate(triggers, 1):
        capability = str(trigger.get("capability") or "").strip()
        if not capability:
            return f"trigger {index} requires capability"
        if {"type", "command", "action"}.intersection(trigger):
            return (
                f"trigger {index} uses action-style or invented fields; trigger "
                "specs use capability plus the fields returned by addTrigger "
                "discovery"
            )
        if capability.casefold() == "time":
            return (
                f"trigger {index} uses unsupported capability='time'; daily "
                "wall-clock triggers require capability='Certain Time (and "
                "optional date)', time='A specific time', and atTime='HH:mm'"
            )
        if capability == "Certain Time (and optional date)":
            mode = trigger.get("time")
            if mode not in {"A specific time", "Sunrise", "Sunset"}:
                return (
                    f"trigger {index} requires time='A specific time', "
                    "'Sunrise', or 'Sunset'"
                )
            if mode == "A specific time":
                at_time = str(trigger.get("atTime") or "")
                # Bare 'HH:mm' recurs daily; a full ISO datetime with a real
                # calendar date fires exactly once and does not recur. Both
                # are valid -- which one is used depends on whether the
                # request was a daily/recurring schedule or a one-time
                # scheduled action (see rule_authoring_service.py).
                is_daily_form = re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", at_time)
                is_one_time_form = re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d", at_time
                )
                if not is_daily_form and not is_one_time_form:
                    return (
                        f"trigger {index} requires atTime as 'HH:mm' (daily) or "
                        "'YYYY-MM-DDTHH:MM:SS' (one-time)"
                    )

    for index, action in enumerate(actions, 1):
        capability = str(action.get("capability") or "").strip()
        if not capability:
            return f"action {index} requires capability"
        if "type" in action:
            return f"action {index} contains unsupported field 'type'"
        if capability.casefold() == "switch":
            if "command" in action:
                return (
                    f"action {index} maps capability='switch' with action=, not "
                    "command=; use capability='runCommand' for a custom driver "
                    "command"
                )
            if action.get("action") not in {
                "on", "off", "toggle", "flash", "setPerMode", "choosePerMode",
            }:
                return f"action {index} has an invalid switch action"
            if not isinstance(action.get("deviceIds"), list) or not action["deviceIds"]:
                return f"action {index} requires non-empty deviceIds"
        if capability == "runCommand":
            if not str(action.get("command") or "").strip():
                return f"action {index} runCommand requires command"
            if not isinstance(action.get("deviceIds"), list) or not action["deviceIds"]:
                return f"action {index} runCommand requires non-empty deviceIds"
            if not str(action.get("capabilityFilter") or "").strip():
                return f"action {index} runCommand requires capabilityFilter"

    daily_times = {
        str(trigger.get("atTime"))
        for trigger in triggers
        if trigger.get("capability") == "Certain Time (and optional date)"
        and trigger.get("time") == "A specific time"
    }
    if len(daily_times) > 1 and len(actions) > 1:
        return (
            "one rule cannot safely pair multiple daily times with multiple "
            "actions: every trigger can run the same action list. Submit one "
            "independently named rule per time/action pair in the same confirmation "
            "group (for example block at 09:00 and allow at 19:00)"
        )
    return None


def rule_machine_proposal_error(
    tool_name: str,
    arguments: dict[str, Any],
) -> str | None:
    """Reject incomplete or invented hub_set_rule writes before confirmation."""

    if tool_name != "hub_manage_rule_machine":
        return None
    if _normalized_operation(arguments.get("tool")) != "hub_set_rule":
        return None
    payload = arguments.get("args")
    if not isinstance(payload, dict):
        return (
            "Invalid Rule Machine proposal: gateway args must be an object. "
            "Read hub_get_tool_guide(section=\"set_rule_reference\") and retry. "
            "No action was queued or executed."
        )
    if "operation" in payload or isinstance(payload.get("args"), dict):
        return (
            "Invalid Rule Machine proposal: hub_set_rule does not use an "
            "operation/create/args envelope. Put name, addTrigger(s), and "
            "addAction(s) directly inside the gateway args object. Read "
            "hub_get_tool_guide(section=\"set_rule_reference\") and retry. "
            "No action was queued or executed."
        )
    if payload.get("confirm") is True:
        return (
            "Invalid Rule Machine proposal: do not send confirm=true from the "
            "model. HomeBrain adds upstream approval only after the user confirms. "
            "No action was queued or executed."
        )
    app_id = payload.get("appId")
    if app_id in {None, ""} and not str(payload.get("name") or "").strip():
        return (
            "Invalid Rule Machine proposal: creating hub_set_rule requires a "
            "non-empty name. Read hub_get_tool_guide"
            "(section=\"set_rule_reference\") and retry with the complete direct "
            "payload. No action was queued or executed."
        )
    mutation_fields = {
        "name", "settings", "button", "buttonRule", "walkStep", "patches",
        "addTrigger", "addTriggers", "addAction", "addActions",
        "addRequiredExpression", "replaceRequiredExpression", "replaceActions",
        "removeAction", "clearActions", "moveAction", "removeTrigger",
        "modifyTrigger", "addLocalVariable", "removeLocalVariable",
    }
    if not mutation_fields.intersection(payload):
        return (
            "Invalid Rule Machine proposal: hub_set_rule contains no rule change. "
            "Read hub_get_tool_guide(section=\"set_rule_reference\") and retry. "
            "No action was queued or executed."
        )
    if app_id in {None, ""} and not {
        "addTrigger", "addTriggers", "addAction", "addActions",
        "addRequiredExpression",
    }.intersection(payload):
        return (
            "Invalid Rule Machine proposal: a new rule must contain at least one "
            "trigger, action, or required expression; an empty shell will not be "
            "queued. Read hub_get_tool_guide(section=\"set_rule_reference\") and "
            "retry. No action was queued or executed."
        )
    shortcut_error = _rule_shortcut_error(payload)
    if shortcut_error is not None:
        return (
            "Invalid Rule Machine proposal: "
            f"{shortcut_error}. Read hub_get_tool_guide sections "
            "'set_rule_reference' and the live addTrigger/addAction discovery "
            "schemas, then retry with direct gateway args. No action was queued "
            "or executed."
        )
    return None


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

    if _is_gateway_schema_probe(name, arguments):
        return ToolEffect.READ
    if _is_rule_capability_probe(name, arguments):
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


def device_resolver_tool() -> MCPTool:
    return MCPTool(
        LOCAL_RESOLVE_TOOL,
        (
            "Resolve one user-supplied Hubitat device name using bounded targeted "
            "label-filtered lookups. Returns the authoritative device ID, label, "
            "capabilities, and commands without loading the full device inventory. "
            "Use this before authoring any rule for a named device. "
            "IMPORTANT: if the request implies the device must be able to perform "
            "a specific command -- e.g. 'block'/'disable'/'restrict' internet "
            "access implies blockInternet, 'allow'/'unblock'/'restore' internet "
            "access implies allowInternet, 'lock' implies lock -- always pass "
            "required_command with that exact command name. A house can contain "
            "two different devices with overlapping or identical names where only "
            "one actually supports the requested command (e.g. a plain power "
            "switch labelled 'TV' next to a separate network-integration device "
            "that is the only one supporting blockInternet/allowInternet); "
            "name-only resolution will confidently return the wrong one. Passing "
            "required_command scopes matching to devices that actually advertise "
            "it, finding the correct device instead."
        ),
        {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Device wording supplied by the user, such as tab s9 fe.",
                },
                "required_command": {
                    "type": "string",
                    "minLength": 1,
                    "description": (
                        "Optional. The exact device command this request requires "
                        "(e.g. blockInternet, allowInternet, lock, unlock). When "
                        "set, resolution is scoped to only the devices that "
                        "actually advertise this command before matching by name, "
                        "so a same-named but incapable device is never returned."
                    ),
                },
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        annotations={"readOnlyHint": True, "effect": ToolEffect.READ.value},
    )


def device_history_tool() -> MCPTool:
    return MCPTool(
        LOCAL_DEVICE_HISTORY_TOOL,
        (
            "Read authoritative recent event history for one named Hubitat "
            "device. The host resolves the name with targeted fuzzy-safe "
            "lookups and calls hub_list_device_events with bounded arguments. "
            "Use this for when, what changed, last on/off, repeated changes, "
            "or why questions about a device. Events prove reported state "
            "transitions but do not by themselves prove what caused them."
        ),
        {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Natural device name supplied by the user.",
                },
                "hours_back": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 168,
                    "default": 24,
                    "description": "Relative history window in hours, up to seven days.",
                },
                "attribute": {
                    "type": "string",
                    "description": "Optional event attribute filter such as switch, motion, contact, or temperature.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                },
            },
            "required": ["name"],
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
