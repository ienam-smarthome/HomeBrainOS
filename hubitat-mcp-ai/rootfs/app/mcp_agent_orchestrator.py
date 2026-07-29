from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from device_state_summary import (
    active_lights,
    active_non_light_switches,
    active_room_summary,
    is_light_device,
    room_name,
)
from deterministic_tool_presenter import present_tool_result
from device_target_resolver import normalized_name, resolve_device_candidate
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult

logger = logging.getLogger("HomeBrainOS.Orchestrator")

_CONFIRM_WORDS = {"confirm", "confirmed", "proceed", "yes", "yes proceed", "do it"}
_SENSITIVE_TERMS = {
    "backup", "delete", "disable", "enable", "factory_reset", "firmware",
    "garage", "lock", "reboot", "restart", "rule", "security", "shutdown", "unlock",
}
_MUTATION_TERMS = {
    "close", "create", "delete", "disable", "enable", "lock", "off", "on",
    "open", "pause", "reboot", "remove", "restart", "resume", "set", "start",
    "stop", "toggle", "unlock", "update", "write",
}
_READ_ONLY_TERMS = {
    "capabilities", "details", "devices", "find", "get", "health", "inventory",
    "list", "read", "rooms", "search", "state", "status",
}
_APP_TERMS = {
    "app", "apps", "automation", "automations", "pause", "paused", "resume",
    "rule", "rules",
}
_DEVICE_TERMS = {
    "battery", "batteries", "device", "devices", "door", "light", "lights",
    "fan", "humidity", "lamp", "lamps", "lock", "motion", "outlet", "plug",
    "presence", "sensor", "state", "switch", "temperature", "thermostat",
    "weather",
}
_DIAGNOSTIC_TERMS = {
    "backup", "cpu", "diagnostic", "diagnostics", "firmware", "health", "log",
    "logs", "matter", "memory", "radio", "software", "update", "updates",
    "version", "zigbee", "zwave",
}
_DEVICE_HEALTH_TERMS = {"offline", "stale", "unavailable"}
_LOG_TERMS = {"log", "logs"}
_ROOM_TERMS = {"room", "rooms"}
_HOME_STATE_PATTERNS = (
    r"\bwhat(?:'s| is) happening\b",
    r"\bhome (?:status|summary|overview)\b",
)
_LOCAL_FILTER_TOOL = "homebrain_filter_devices"
_LOCAL_ACTIVE_LIGHTS_TOOL = "homebrain_active_lights"
_LOCAL_ACTIVE_ROOMS_TOOL = "homebrain_active_rooms"
_LOCAL_ACTIVE_SWITCHES_TOOL = "homebrain_active_switches"
_LOCAL_CONTROL_TOOL = "homebrain_control_devices"
_LOCAL_HUB_INFO_TOOL = "homebrain_hub_info_snapshot"


@dataclass(slots=True)
class PendingConfirmation:
    expires_at: float
    actions: list[tuple[str, dict[str, Any]]]
    messages: list[dict[str, Any]]
    assistant_message: dict[str, Any]


@dataclass(slots=True)
class AgentOutcome:
    message: str
    request_class: str
    evidence: list[dict[str, Any]]


class UnifiedMCPAgent:
    """Ollama Online agent that executes live Hubitat MCP function calls."""

    def __init__(
        self,
        mcp_client: HubitatMCPClient,
        api_key: str,
        model_name: str = "gemma4:31b",
        *,
        base_url: str = "https://ollama.com",
        timeout_seconds: float = 60,
        stream_idle_timeout_seconds: float = 20,
        tool_limit: int = 48,
        max_tool_rounds: int = 6,
        require_sensitive_confirmation: bool = True,
        confirmation_ttl_seconds: float = 120,
        max_tool_result_chars: int = 24000,
        ai_client: Any | None = None,
    ) -> None:
        self.mcp = mcp_client
        self.api_key = str(api_key or "").strip()
        self.model_name = str(model_name or "").strip()
        if self.model_name.lower().endswith("-cloud"):
            self.model_name = self.model_name[:-6]
        self.base_url = str(base_url or "https://ollama.com").rstrip("/")
        self.timeout_seconds = max(3.0, float(timeout_seconds))
        self.stream_idle_timeout_seconds = max(
            1.0, float(stream_idle_timeout_seconds)
        )
        self.tool_limit = max(1, int(tool_limit))
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.require_sensitive_confirmation = bool(require_sensitive_confirmation)
        self.confirmation_ttl_seconds = max(10.0, float(confirmation_ttl_seconds))
        self.max_tool_result_chars = max(2000, int(max_tool_result_chars))
        self._pending: dict[str, PendingConfirmation] = {}
        self._app_manifest: list[dict[str, Any]] = []
        self._app_manifest_at = 0.0
        self._evidence: ContextVar[list[dict[str, Any]] | None] = ContextVar(
            "hubitat_evidence", default=None
        )
        self._request_class: ContextVar[str] = ContextVar(
            "hubitat_request_class", default="live-read"
        )
        self.ai_client = ai_client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model_name and self.base_url)

    async def close(self) -> None:
        close = getattr(self.ai_client, "aclose", None)
        if callable(close):
            await close()

    @staticmethod
    def _matches(prompt: str, terms: set[str]) -> bool:
        value = prompt.lower()
        return any(
            re.search(
                rf"\b{re.escape(term.lower())}(?:s|es)?\b", value
            ) is not None
            for term in terms
        )

    @staticmethod
    def _requests_mutation(prompt: str) -> bool:
        value = " ".join(prompt.lower().split())
        strong_verbs = {
            "create", "delete", "disable", "enable", "install", "pause", "reboot", "remove",
            "restart", "resume", "set", "shutdown", "start", "stop", "toggle",
            "unlock", "update", "write",
        }
        tokens = re.findall(r"[a-z0-9]+", value)
        if tokens and tokens[0] in strong_verbs | {"close", "lock", "open"}:
            return True
        if re.search(r"\b(?:turn|switch|power)\b.+\b(?:on|off)\b", value):
            return True
        if re.search(
            r"\bplease\s+(?:close|create|delete|disable|enable|install|lock|open|pause|"
            r"reboot|remove|restart|resume|set|shutdown|start|stop|toggle|"
            r"unlock|update|write)\b",
            value,
        ):
            return True
        return False

    def _classify_request(self, prompt: str, session_id: str) -> str:
        normalized = " ".join(prompt.strip().lower().split())
        if (
            self._requests_mutation(prompt)
            or (
                normalized in _CONFIRM_WORDS
                and session_id in self._pending
            )
        ):
            return "write"
        conversational = (
            r"(?:hi|hello|hey|thanks|thank you|good morning|good evening)[.!? ]*",
            r"(?:help|what can you do|who are you)[.!? ]*",
        )
        if any(re.fullmatch(pattern, normalized) for pattern in conversational):
            return "conversational"
        # This is a Hubitat assistant: an unmatched factual request is safer when
        # treated as a live read than when the model is allowed to answer from memory.
        return "live-read"

    @staticmethod
    def _redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): (
                    "[redacted]"
                    if any(part in str(key).lower() for part in (
                        "authorization", "password", "secret", "token", "api_key",
                    ))
                    else UnifiedMCPAgent._redact(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [UnifiedMCPAgent._redact(item) for item in value[:20]]
        rendered = value
        if isinstance(rendered, str) and len(rendered) > 240:
            return rendered[:237] + "..."
        return rendered

    @staticmethod
    def _result_summary(result: MCPToolResult) -> str:
        data = result.data
        if isinstance(data, dict):
            keys = ", ".join(map(str, list(data)[:10]))
            return f"object fields: {keys}" if keys else "empty object"
        if isinstance(data, list):
            return f"{len(data)} result items"
        text = str(result.text or data or "").strip()
        return (text[:157] + "...") if len(text) > 160 else (text or "empty result")

    def _record_evidence(
        self,
        gateway: str,
        arguments: dict[str, Any],
        *,
        success: bool,
        elapsed_ms: int,
        summary: str,
        supports_live_claim: bool = True,
        evidence_kind: str = "tool_result",
    ) -> None:
        receipts = self._evidence.get()
        if receipts is None:
            return
        receipts.append({
            "tool": gateway,
            "sub_tool": arguments.get("tool"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": elapsed_ms,
            "success": success,
            "supports_live_claim": supports_live_claim,
            "evidence_kind": evidence_kind,
            "arguments": self._redact(arguments),
            "summary": summary,
        })

    def _has_live_evidence(self) -> bool:
        return any(
            receipt.get("success") and receipt.get("supports_live_claim")
            for receipt in (self._evidence.get() or [])
        )

    @staticmethod
    def _device_filter_tool() -> MCPTool:
        return MCPTool(
            _LOCAL_FILTER_TOOL,
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

    @staticmethod
    def _active_rooms_tool() -> MCPTool:
        return MCPTool(
            _LOCAL_ACTIVE_ROOMS_TOOL,
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

    @staticmethod
    def _active_lights_tool() -> MCPTool:
        return MCPTool(
            _LOCAL_ACTIVE_LIGHTS_TOOL,
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

    @staticmethod
    def _active_switches_tool() -> MCPTool:
        return MCPTool(
            _LOCAL_ACTIVE_SWITCHES_TOOL,
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

    @staticmethod
    def _control_devices_tool() -> MCPTool:
        return MCPTool(
            _LOCAL_CONTROL_TOOL,
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
                        "enum": ["light", "switch"],
                        "description": "Whether targets must be lights or non-light switches.",
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
            annotations={"readOnlyHint": False, "destructiveHint": False},
        )

    @staticmethod
    def _hub_info_tool() -> MCPTool:
        return MCPTool(
            _LOCAL_HUB_INFO_TOOL,
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

    @staticmethod
    def _device_attributes(device: dict[str, Any]) -> dict[str, Any]:
        attributes = (
            device.get("attributes")
            or device.get("currentStates")
            or device.get("states")
            or {}
        )
        if isinstance(attributes, list):
            return {
                str(item.get("name")): item.get(
                    "currentValue", item.get("value")
                )
                for item in attributes
                if isinstance(item, dict) and item.get("name")
            }
        return dict(attributes) if isinstance(attributes, dict) else {}

    @staticmethod
    def _hub_info_device(
        devices: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        matches = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            label = str(
                device.get("label")
                or device.get("displayName")
                or device.get("name")
                or ""
            )
            normalized = normalized_name(label)
            if normalized.startswith("hubinfo"):
                matches.append(device)
        return matches[0] if len(matches) == 1 else None

    async def _hub_info_snapshot(
        self, arguments: dict[str, Any]
    ) -> MCPToolResult:
        scope = str(arguments.get("scope") or "").strip().lower()
        if scope not in {"firmware", "resources", "full"}:
            return MCPToolResult(
                _LOCAL_HUB_INFO_TOOL,
                arguments,
                {},
                "Invalid Hub Info scope",
                {"success": False, "error": "scope must be firmware, resources, or full"},
                is_error=True,
            )
        try:
            cached = await self.mcp.get_cached_devices()
        except Exception as exc:
            cached = []
            logger.warning("Could not load Hub Info identity manifest: %s", exc)
        hub_device = self._hub_info_device(list(cached or []))
        if hub_device is None:
            source = await self.mcp.call_tool(
                "hub_read_devices",
                {"tool": "hub_list_devices", "args": {"labelFilter": "Hub Info"}},
            )
            hub_device = self._hub_info_device(
                [
                    item
                    for item in (
                        HubitatMCPClient._find_device_list(source.data) or []
                    )
                    if isinstance(item, dict)
                ]
            )
        if hub_device is None:
            return MCPToolResult(
                _LOCAL_HUB_INFO_TOOL,
                arguments,
                {},
                "Hub Info device not found",
                {
                    "success": False,
                    "error": (
                        "A unique Hub Info device could not be found. Install or "
                        "rename the Hub Information Driver device."
                    ),
                },
                is_error=True,
            )
        device_id = str(
            hub_device.get("id") or hub_device.get("deviceId") or ""
        )
        label = str(
            hub_device.get("label")
            or hub_device.get("displayName")
            or hub_device.get("name")
            or "Hub Info"
        )
        if not device_id:
            return MCPToolResult(
                _LOCAL_HUB_INFO_TOOL,
                arguments,
                {},
                "Hub Info device has no device ID",
                {"success": False, "error": "Hub Info device has no device ID"},
                is_error=True,
            )
        cached_attributes = self._device_attributes(hub_device)
        baseline_firmware = (
            cached_attributes.get("hubUpdateStatus"),
            cached_attributes.get("hubUpdateVersion"),
        )

        commands = []
        if scope in {"resources", "full"}:
            commands.append("refresh")
        if scope in {"firmware", "full"}:
            commands.append("updateCheck")
        for command in commands:
            result = await self.mcp.call_tool(
                "hub_manage_devices",
                {
                    "tool": "hub_call_device_command",
                    "args": {"deviceId": device_id, "command": command},
                },
            )
            if not self._tool_succeeded(result):
                return MCPToolResult(
                    _LOCAL_HUB_INFO_TOOL,
                    arguments,
                    {},
                    result.text,
                    {
                        "success": False,
                        "error": (
                            f"Hub Info command {command!r} failed: "
                            f"{result.text or 'unknown error'}"
                        ),
                    },
                    is_error=True,
                )

        live_device: dict[str, Any] | None = None
        poll_attempts = 10 if scope in {"firmware", "full"} else 6
        for attempt in range(poll_attempts):
            source = await self.mcp.call_tool(
                "hub_read_devices",
                {
                    "tool": "hub_list_devices",
                    "args": {"labelFilter": label},
                },
            )
            candidates = [
                item
                for item in (
                    HubitatMCPClient._find_device_list(source.data) or []
                )
                if isinstance(item, dict)
            ]
            live_device = self._hub_info_device(candidates)
            if live_device is not None:
                attributes = self._device_attributes(live_device)
                refreshed_firmware = (
                    attributes.get("hubUpdateStatus"),
                    attributes.get("hubUpdateVersion"),
                )
                firmware_settled = (
                    refreshed_firmware != baseline_firmware
                    or attempt == poll_attempts - 1
                )
                if (
                    scope not in {"firmware", "full"}
                    or (
                        all(value is not None for value in refreshed_firmware)
                        and firmware_settled
                    )
                ):
                    break
            if attempt < poll_attempts - 1:
                await asyncio.sleep(0.5)
        if live_device is None:
            return MCPToolResult(
                _LOCAL_HUB_INFO_TOOL,
                arguments,
                {},
                "Hub Info attributes unavailable after refresh",
                {
                    "success": False,
                    "error": "Hub Info attributes were unavailable after refresh",
                },
                is_error=True,
            )
        values = {
            **live_device,
            **self._device_attributes(live_device),
        }

        def value(*names: str) -> Any:
            return next(
                (
                    values.get(name)
                    for name in names
                    if values.get(name) is not None
                    and values.get(name) != ""
                ),
                None,
            )

        installed = value("firmwareVersionString", "firmwareVersion")
        available = value("hubUpdateVersion")
        update_status = value("hubUpdateStatus")
        update_available = (
            "available" in str(update_status or "").casefold()
            or (
                bool(installed)
                and bool(available)
                and str(installed) != str(available)
            )
        )
        data = {
            "success": True,
            "source": label,
            "device_id": device_id,
            "scope": scope,
            "installed_firmware": installed,
            "update_status": update_status,
            "available_firmware": available,
            "update_available": update_available,
            "hub_model": value("hubModel"),
            "cpu_5_min": value("cpu5Min"),
            "cpu_percent": value("cpuPct"),
            "cpu_15_min": value("cpu15Min"),
            "cpu_15_percent": value("cpu15Pct"),
            "free_memory": value("freeMemory"),
            "free_memory_15_min": value("freeMem15"),
            "jvm_free": value("jvmFree"),
            "jvm_size": value("jvmSize"),
            "java_direct": value("javaDirect"),
            "temperature": value("temperature", "temperatureC"),
            "uptime": value("formattedUptime", "uptime"),
            "database_size": value("dbSize"),
            "ip_address": value("localIP", "ipAddress"),
            "zigbee_healthy": value("zbHealthy"),
            "zwave_healthy": value("zwHealthy"),
            "hub_alerts": value("hubAlerts"),
            "matter_status": value("matterStatus"),
            "last_poll": value("lastPollTime"),
        }
        return MCPToolResult(
            _LOCAL_HUB_INFO_TOOL, arguments, {}, json.dumps(data), data
        )

    @staticmethod
    def _normalized_attribute(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    @classmethod
    def _attribute_matches(
        cls, actual: Any, operator: str, expected: Any
    ) -> bool:
        if operator == "exists":
            return actual is not None
        if operator == "not_exists":
            return actual is None
        if actual is None:
            return False
        if operator in {"lt", "lte", "gt", "gte"}:
            left, right = float(actual), float(expected)
            return {
                "lt": left < right,
                "lte": left <= right,
                "gt": left > right,
                "gte": left >= right,
            }[operator]
        if operator == "contains":
            return str(expected).casefold() in str(actual).casefold()
        try:
            left_value: Any = float(actual)
            right_value: Any = float(expected)
        except (TypeError, ValueError):
            left_value = str(actual).casefold()
            right_value = str(expected).casefold()
        return left_value == right_value if operator == "eq" else left_value != right_value

    async def _filter_devices(
        self, arguments: dict[str, Any]
    ) -> MCPToolResult:
        attribute = str(arguments.get("attribute") or "").strip()
        operator = str(arguments.get("operator") or "").strip().lower()
        expected = arguments.get("value")
        valid = {
            "eq", "ne", "lt", "lte", "gt", "gte",
            "contains", "exists", "not_exists",
        }
        if not attribute or operator not in valid:
            return MCPToolResult(
                _LOCAL_FILTER_TOOL, arguments, {}, "Invalid filter arguments",
                {"error": "attribute and a valid operator are required"},
                is_error=True,
            )
        if operator not in {"exists", "not_exists"} and "value" not in arguments:
            return MCPToolResult(
                _LOCAL_FILTER_TOOL, arguments, {}, "Comparison value required",
                {"error": "value is required for this operator"},
                is_error=True,
            )
        source_arguments = {"tool": "hub_list_devices", "args": {}}
        started = time.monotonic()
        source = await self.mcp.call_tool("hub_read_devices", source_arguments)
        devices = [
            item
            for item in (
                HubitatMCPClient._find_device_list(source.data) or []
            )
            if isinstance(item, dict)
        ]
        self._record_evidence(
            "hub_read_devices",
            source_arguments,
            success=self._tool_succeeded(source),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(devices)} source device records",
            evidence_kind="authoritative_state_snapshot",
        )
        if not self._tool_succeeded(source):
            return MCPToolResult(
                _LOCAL_FILTER_TOOL, arguments, {}, source.text,
                {"error": source.text or "Live device read failed"},
                is_error=True,
            )
        wanted = self._normalized_attribute(attribute)
        matches: list[dict[str, Any]] = []
        comparison_errors = 0
        for device in devices:
            attributes = self._device_attributes(device)
            actual = next(
                (
                    value for key, value in attributes.items()
                    if self._normalized_attribute(str(key)) == wanted
                ),
                None,
            )
            if actual is None:
                actual = next(
                    (
                        value for key, value in device.items()
                        if self._normalized_attribute(str(key)) == wanted
                    ),
                    None,
                )
            try:
                matched = self._attribute_matches(actual, operator, expected)
            except (TypeError, ValueError):
                comparison_errors += 1
                continue
            if matched:
                matches.append({
                    "id": device.get("id") or device.get("deviceId"),
                    "label": device.get("label") or device.get("name"),
                    "room": device.get("room") or device.get("roomName"),
                    "attribute": attribute,
                    "value": actual,
                })
        data = {
            "attribute": attribute,
            "operator": operator,
            "comparison_value": expected,
            "matches": matches,
            "count": len(matches),
            "total_scanned": len(devices),
            "comparison_errors": comparison_errors,
            "complete": True,
        }
        return MCPToolResult(
            _LOCAL_FILTER_TOOL, arguments, {}, json.dumps(data), data
        )

    async def _active_lights(self, arguments: dict[str, Any]) -> MCPToolResult:
        source_arguments = {"tool": "hub_list_devices", "args": {}}
        started = time.monotonic()
        source = await self.mcp.call_tool("hub_read_devices", source_arguments)
        devices = [
            item
            for item in (HubitatMCPClient._find_device_list(source.data) or [])
            if isinstance(item, dict)
        ]
        self._record_evidence(
            "hub_read_devices",
            source_arguments,
            success=self._tool_succeeded(source),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(devices)} source device records",
            evidence_kind="authoritative_state_snapshot",
        )
        if not self._tool_succeeded(source):
            return MCPToolResult(
                _LOCAL_ACTIVE_LIGHTS_TOOL,
                arguments,
                {},
                source.text,
                {"error": source.text or "Live device read failed"},
                is_error=True,
            )
        lights = active_lights(devices)
        data = {
            "lights": lights,
            "count": len(lights),
            "definition": "light/bulb capability with switch=on",
            "total_scanned": len(devices),
            "complete": True,
        }
        return MCPToolResult(
            _LOCAL_ACTIVE_LIGHTS_TOOL, arguments, {}, json.dumps(data), data
        )

    async def _active_rooms(self, arguments: dict[str, Any]) -> MCPToolResult:
        source_arguments = {"tool": "hub_list_devices", "args": {}}
        started = time.monotonic()
        source = await self.mcp.call_tool("hub_read_devices", source_arguments)
        devices = [
            item
            for item in (HubitatMCPClient._find_device_list(source.data) or [])
            if isinstance(item, dict)
        ]
        self._record_evidence(
            "hub_read_devices",
            source_arguments,
            success=self._tool_succeeded(source),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(devices)} source device records",
            evidence_kind="authoritative_state_snapshot",
        )
        if not self._tool_succeeded(source):
            return MCPToolResult(
                _LOCAL_ACTIVE_ROOMS_TOOL,
                arguments,
                {},
                source.text,
                {"error": source.text or "Live device read failed"},
                is_error=True,
            )
        rooms = active_room_summary(devices)
        data = {
            "active_rooms": rooms,
            "count": len(rooms),
            "definition": "motion=active OR light switch=on",
            "total_scanned": len(devices),
            "complete": True,
        }
        return MCPToolResult(
            _LOCAL_ACTIVE_ROOMS_TOOL, arguments, {}, json.dumps(data), data
        )

    async def _active_switches(self, arguments: dict[str, Any]) -> MCPToolResult:
        source_arguments = {"tool": "hub_list_devices", "args": {}}
        started = time.monotonic()
        source = await self.mcp.call_tool("hub_read_devices", source_arguments)
        devices = [
            item
            for item in (HubitatMCPClient._find_device_list(source.data) or [])
            if isinstance(item, dict)
        ]
        self._record_evidence(
            "hub_read_devices",
            source_arguments,
            success=self._tool_succeeded(source),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=f"{len(devices)} source device records",
            evidence_kind="authoritative_state_snapshot",
        )
        if not self._tool_succeeded(source):
            return MCPToolResult(
                _LOCAL_ACTIVE_SWITCHES_TOOL,
                arguments,
                {},
                source.text,
                {"error": source.text or "Live device read failed"},
                is_error=True,
            )
        switches = active_non_light_switches(devices)
        data = {
            "switches": switches,
            "count": len(switches),
            "definition": "switch=on excluding light/bulb capabilities",
            "total_scanned": len(devices),
            "complete": True,
        }
        return MCPToolResult(
            _LOCAL_ACTIVE_SWITCHES_TOOL, arguments, {}, json.dumps(data), data
        )

    @staticmethod
    def _is_switch_device(device: dict[str, Any]) -> bool:
        capabilities = device.get("capabilities") or []
        if isinstance(capabilities, dict):
            capabilities = list(capabilities)
        elif isinstance(capabilities, str):
            capabilities = [capabilities]
        capability_text = " ".join(
            str(item.get("name") if isinstance(item, dict) else item)
            for item in capabilities
        ).casefold()
        return "switch" in capability_text

    async def _control_devices(
        self, arguments: dict[str, Any]
    ) -> MCPToolResult:
        room = str(arguments.get("room") or "").strip()
        names = arguments.get("device_names") or []
        kind = str(arguments.get("device_kind") or "").strip().lower()
        command = str(arguments.get("command") or "").strip()
        if (
            bool(room) == bool(names)
            or not isinstance(names, list)
            or kind not in {"light", "switch"}
            or command not in {"on", "off", "toggle"}
        ):
            return MCPToolResult(
                _LOCAL_CONTROL_TOOL,
                arguments,
                {},
                "Invalid control arguments",
                {
                    "success": False,
                    "error": (
                        "Provide exactly one of room or device_names, plus a valid "
                        "device_kind and command."
                    ),
                },
                is_error=True,
            )

        lookup_arguments = (
            [{"tool": "hub_list_devices", "args": {}}]
            if room
            else [
                {
                    "tool": "hub_list_devices",
                    "args": {"labelFilter": str(requested)},
                }
                for requested in names
            ]
        )

        async def lookup(
            source_arguments: dict[str, Any]
        ) -> tuple[MCPToolResult, int]:
            started = time.monotonic()
            source = await self.mcp.call_tool(
                "hub_read_devices", source_arguments
            )
            return source, round((time.monotonic() - started) * 1000)

        sources = await asyncio.gather(
            *(lookup(source_arguments) for source_arguments in lookup_arguments)
        )
        devices: list[dict[str, Any]] = []
        source_groups: list[list[dict[str, Any]]] = []
        lookup_errors: list[str] = []
        seen_source_ids: set[str] = set()
        for source_arguments, (source, elapsed_ms) in zip(
            lookup_arguments, sources, strict=True
        ):
            source_devices = [
                item
                for item in (
                    HubitatMCPClient._find_device_list(source.data) or []
                )
                if isinstance(item, dict)
            ]
            source_groups.append(source_devices)
            succeeded = self._tool_succeeded(source)
            self._record_evidence(
                "hub_read_devices",
                source_arguments,
                success=succeeded,
                elapsed_ms=elapsed_ms,
                summary=f"{len(source_devices)} target candidates",
                supports_live_claim=False,
                evidence_kind="control_target_resolution",
            )
            if not succeeded:
                lookup_errors.append(
                    source.text or "Hubitat target lookup failed."
                )
                continue
            for device in source_devices:
                source_id = str(
                    device.get("id") or device.get("deviceId") or id(device)
                )
                if source_id not in seen_source_ids:
                    seen_source_ids.add(source_id)
                    devices.append(device)
        if lookup_errors:
            data = {
                "success": False,
                "error": " ".join(lookup_errors),
                "matched": [],
                "executed": 0,
            }
            return MCPToolResult(
                _LOCAL_CONTROL_TOOL, arguments, {}, json.dumps(data), data,
                is_error=True,
            )

        candidates = [
            device for device in devices
            if (
                is_light_device(device)
                if kind == "light"
                else self._is_switch_device(device) and not is_light_device(device)
            )
        ]
        targets: list[dict[str, Any]] = []
        resolution_errors: list[str] = []
        if room:
            wanted_room = normalized_name(room)
            targets = [
                device for device in candidates
                if normalized_name(room_name(device)) == wanted_room
            ]
            if not targets:
                started = time.monotonic()
                try:
                    manifest = await self.mcp.get_cached_devices()
                except Exception as exc:
                    self._record_evidence(
                        "hub_read_devices",
                        {
                            "tool": "hub_list_devices",
                            "source": "short_ttl_cache",
                        },
                        success=False,
                        elapsed_ms=round(
                            (time.monotonic() - started) * 1000
                        ),
                        summary=f"Room identity manifest unavailable: {exc}",
                        supports_live_claim=False,
                        evidence_kind="control_target_resolution",
                    )
                else:
                    room_candidates = [
                        device
                        for device in (manifest or [])
                        if isinstance(device, dict)
                        and normalized_name(room_name(device)) == wanted_room
                        and (
                            is_light_device(device)
                            if kind == "light"
                            else (
                                self._is_switch_device(device)
                                and not is_light_device(device)
                            )
                        )
                    ]
                    self._record_evidence(
                        "hub_read_devices",
                        {
                            "tool": "hub_list_devices",
                            "source": "short_ttl_cache",
                        },
                        success=True,
                        elapsed_ms=round(
                            (time.monotonic() - started) * 1000
                        ),
                        summary=(
                            f"{len(room_candidates)} {kind} candidates in "
                            f"normalized room {room!r}"
                        ),
                        supports_live_claim=False,
                        evidence_kind="control_target_resolution",
                    )
                    targets = room_candidates
                if not targets:
                    resolution_errors.append(
                        f"No {kind}s were found in room {room!r}."
                    )
        else:
            fallback_candidates: list[dict[str, Any]] | None = None
            for requested, source_devices in zip(
                names, source_groups, strict=True
            ):
                eligible = [
                    device for device in source_devices
                    if (
                        is_light_device(device)
                        if kind == "light"
                        else (
                            self._is_switch_device(device)
                            and not is_light_device(device)
                        )
                    )
                ]
                resolution = resolve_device_candidate(
                    str(requested), eligible
                )
                if resolution.target is None:
                    if fallback_candidates is None:
                        started = time.monotonic()
                        try:
                            manifest = await self.mcp.get_cached_devices()
                        except Exception as exc:
                            fallback_candidates = []
                            self._record_evidence(
                                "hub_read_devices",
                                {
                                    "tool": "hub_list_devices",
                                    "source": "short_ttl_cache",
                                },
                                success=False,
                                elapsed_ms=round(
                                    (time.monotonic() - started) * 1000
                                ),
                                summary=f"Identity manifest unavailable: {exc}",
                                supports_live_claim=False,
                                evidence_kind="control_target_resolution",
                            )
                        else:
                            fallback_candidates = [
                                device
                                for device in (manifest or [])
                                if isinstance(device, dict)
                                and (
                                    is_light_device(device)
                                    if kind == "light"
                                    else (
                                        self._is_switch_device(device)
                                        and not is_light_device(device)
                                    )
                                )
                            ]
                            self._record_evidence(
                                "hub_read_devices",
                                {
                                    "tool": "hub_list_devices",
                                    "source": "short_ttl_cache",
                                },
                                success=True,
                                elapsed_ms=round(
                                    (time.monotonic() - started) * 1000
                                ),
                                summary=(
                                    f"{len(fallback_candidates)} fallback "
                                    "target candidates"
                                ),
                                supports_live_claim=False,
                                evidence_kind="control_target_resolution",
                            )
                    resolution = resolve_device_candidate(
                        str(requested), fallback_candidates
                    )
                if resolution.target is not None:
                    target = dict(resolution.target)
                    target["_resolved_label"] = resolution.matched_name
                    targets.append(target)
                else:
                    resolution_errors.append(resolution.reason)

        unique_targets: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for target in targets:
            device_id = str(target.get("id") or target.get("deviceId") or "")
            if not device_id:
                resolution_errors.append(
                    f"{target.get('label') or target.get('name')!r} has no device ID."
                )
            elif device_id not in seen_ids:
                seen_ids.add(device_id)
                unique_targets.append(target)
        if resolution_errors:
            data = {
                "success": False,
                "error": " ".join(resolution_errors),
                "matched": [],
                "executed": 0,
            }
            return MCPToolResult(
                _LOCAL_CONTROL_TOOL, arguments, {}, json.dumps(data), data,
                is_error=True,
            )

        semaphore = asyncio.Semaphore(8)

        async def execute(target: dict[str, Any]) -> dict[str, Any]:
            device_id = str(target.get("id") or target.get("deviceId"))
            label = str(
                target.get("_resolved_label")
                or target.get("label")
                or target.get("name")
                or device_id
            )
            call_arguments = {
                "tool": "hub_call_device_command",
                "args": {"deviceId": device_id, "command": command},
            }
            started = time.monotonic()
            command_success = False
            verified: bool | None = None
            verification_message = ""
            try:
                async with semaphore:
                    result = await self.mcp.call_tool(
                        "hub_manage_devices", call_arguments
                    )
                command_success = self._tool_succeeded(result)
                message = result.text
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                logger.exception(
                    "High-level device command failed for %s", label
                )
            self._record_evidence(
                "hub_manage_devices",
                call_arguments,
                success=command_success,
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=(
                    f"{command} {label}: "
                    f"{'success' if command_success else 'failed'}"
                ),
                supports_live_claim=True,
                evidence_kind="device_command_result",
            )
            if command_success and command in {"on", "off"}:
                verify_arguments = {
                    "tool": "hub_get_device_attribute",
                    "args": {
                        "deviceId": device_id,
                        "attribute": "switch",
                        "expectedValue": command,
                    },
                }
                verify_started = time.monotonic()
                try:
                    async with semaphore:
                        verification = await self.mcp.call_tool(
                            "hub_manage_devices", verify_arguments
                        )
                    verified = self._tool_succeeded(verification)
                    verification_message = verification.text
                except Exception as exc:
                    verified = False
                    verification_message = f"{type(exc).__name__}: {exc}"
                    logger.exception(
                        "High-level device verification failed for %s", label
                    )
                self._record_evidence(
                    "hub_manage_devices",
                    verify_arguments,
                    success=bool(verified),
                    elapsed_ms=round(
                        (time.monotonic() - verify_started) * 1000
                    ),
                    summary=(
                        f"verify {label} switch={command}: "
                        f"{'success' if verified else 'failed'}"
                    ),
                    supports_live_claim=True,
                    evidence_kind="device_state_verification",
                )
            success = command_success and verified is not False
            return {
                "id": device_id,
                "label": label,
                "room": room_name(target),
                "success": success,
                "command_sent": command_success,
                "verified": verified,
                "message": message,
                "verification_message": verification_message,
            }

        results = await asyncio.gather(*(execute(target) for target in unique_targets))
        succeeded = [item for item in results if item["success"]]
        failed = [item for item in results if not item["success"]]
        data = {
            "success": not failed and bool(succeeded),
            "command": command,
            "device_kind": kind,
            "matched": len(unique_targets),
            "executed": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "complete": True,
        }
        return MCPToolResult(
            _LOCAL_CONTROL_TOOL, arguments, {}, json.dumps(data), data
        )

    @classmethod
    def _needs_device_manifest(cls, prompt: str) -> bool:
        return cls._matches(prompt, _DEVICE_TERMS) or any(
            re.search(pattern, prompt.lower()) is not None
            for pattern in _HOME_STATE_PATTERNS
        )

    def _include_identity_manifest(self, prompt: str) -> bool:
        """Keep live-read facts behind tools instead of prompt-injected state."""

        tokens = set(re.findall(r"[a-z0-9]+", prompt.casefold()))
        routine_control = (
            self._requests_mutation(prompt)
            and bool(tokens & {"on", "off", "toggle"})
            and not bool(tokens & {"garage", "lock", "security", "unlock"})
        )
        return (
            self._needs_device_manifest(prompt)
            and self._request_class.get() == "write"
            and not routine_control
        )

    @classmethod
    def _call_is_mutation(
        cls, tool: MCPTool | None, arguments: dict[str, Any]
    ) -> bool:
        if not tool or (tool.annotations or {}).get("readOnlyHint") is True:
            return False
        name = tool.name.lower().replace("-", "_")
        tokens = set(re.findall(r"[a-z0-9]+", str(arguments).lower()))
        return (
            bool(tokens & _MUTATION_TERMS)
            or name.startswith(("set_", "create_", "delete_", "update_"))
            or name == "hub_update_firmware"
            or name == _LOCAL_CONTROL_TOOL
            or "_manage_" in name
        )

    @staticmethod
    def _tool_succeeded(result: MCPToolResult) -> bool:
        if result.is_error:
            return False
        data = result.data
        if isinstance(data, dict):
            if data.get("success") is False or data.get("error"):
                return False
            for key in ("result", "data", "output"):
                nested = data.get(key)
                if isinstance(nested, dict) and (
                    nested.get("success") is False or nested.get("error")
                ):
                    return False
        return True

    @staticmethod
    def _is_live_log_call(name: str, arguments: dict[str, Any]) -> bool:
        if name != "hub_read_diagnostics":
            return False
        return str(arguments.get("tool") or "") == "hub_get_logs"

    @classmethod
    def _select_tools(cls, prompt: str, tools: list[MCPTool]) -> list[MCPTool]:
        names: set[str] | None = None
        if cls._matches(prompt, _DEVICE_HEALTH_TERMS):
            names = {
                "hub_read_devices", "hub_read_diagnostics",
                "hub_manage_devices",
            }
        elif cls._matches(prompt, _APP_TERMS):
            names = {
                "hub_read_apps_code", "hub_read_rules",
                "hub_search_tools",
            }
            if cls._requests_mutation(prompt):
                names.update({
                    "hub_manage_native_rules_and_apps",
                    "hub_manage_rule_machine",
                })
        elif cls._matches(prompt, _DEVICE_TERMS):
            names = {
                "hub_read_devices", "hub_get_info",
            }
            if cls._requests_mutation(prompt):
                names.add("hub_manage_devices")
        elif cls._matches(prompt, _ROOM_TERMS):
            names = {
                "hub_read_rooms", "hub_search_tools",
            }
            if cls._requests_mutation(prompt):
                names.add("hub_manage_rooms")
        elif cls._matches(prompt, _DIAGNOSTIC_TERMS):
            names = {
                "hub_get_info", "hub_read_diagnostics", "hub_search_tools",
            }
            if cls._requests_mutation(prompt):
                names.update({
                    "hub_manage_diagnostics", "hub_manage_logs",
                    "hub_manage_radio", "hub_manage_destructive_ops",
                    "hub_update_firmware",
                })
        elif (
            cls._requests_mutation(prompt)
            and not cls._matches(prompt, _SENSITIVE_TERMS)
        ):
            # Generic device writes (for example "turn on the TV") should not
            # enter tool discovery merely because the noun is absent from a
            # hand-maintained device vocabulary.
            names = {_LOCAL_CONTROL_TOOL}
        else:
            names = {"hub_get_info", "hub_search_tools"}
        selected = [tool for tool in tools if tool.name in names]
        return selected or tools

    async def _cached_app_manifest(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        if self._app_manifest and now - self._app_manifest_at < 300:
            return list(self._app_manifest)
        names = {tool.name for tool in await self.mcp.list_tools()}
        if "hub_read_apps_code" not in names:
            return []
        try:
            started = time.monotonic()
            result = await self.mcp.call_tool(
                "hub_read_apps_code",
                {"tool": "hub_list_apps", "args": {"scope": "instances"}},
            )
            self._record_evidence(
                "hub_read_apps_code",
                {"tool": "hub_list_apps", "args": {"scope": "instances"}},
                success=self._tool_succeeded(result),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                summary=self._result_summary(result),
                supports_live_claim=False,
            )
            candidates = HubitatMCPClient._find_device_list(result.data) or []
            self._app_manifest = [
                item for item in candidates if isinstance(item, dict)
            ]
            self._app_manifest_at = now
        except Exception as exc:
            logger.warning("Could not build app manifest: %s", exc)
        return list(self._app_manifest)

    async def _system_prompt(self, user_prompt: str = "") -> str:
        rows: list[str] = []
        if self._include_identity_manifest(user_prompt):
            try:
                started = time.monotonic()
                devices = await self.mcp.get_cached_devices()
                self._record_evidence(
                    "hub_read_devices",
                    {
                        "tool": "hub_list_devices",
                        "source": "short_ttl_cache",
                    },
                    success=True,
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=f"{len(devices)} identity records",
                    supports_live_claim=False,
                    evidence_kind="identity_manifest",
                )
                for device in devices:
                    label = device.get("label") or device.get("name") or "Unknown device"
                    device_id = device.get("id") or device.get("deviceId")
                    room = device.get("room") or device.get("roomName") or "Unassigned"
                    capabilities = device.get("capabilities") or []
                    if isinstance(capabilities, dict):
                        capabilities = list(capabilities)
                    if not isinstance(capabilities, list):
                        capabilities = [capabilities]
                    attributes = device.get("attributes") or device.get("currentStates") or {}
                    if isinstance(attributes, list):
                        attributes = {
                            str(item.get("name")): item.get(
                                "currentValue", item.get("value")
                            )
                            for item in attributes
                            if isinstance(item, dict) and item.get("name")
                        }
                    if not isinstance(attributes, dict):
                        attributes = {}
                    common = {
                        "battery", "condition", "contact", "humidity", "level",
                        "healthstatus", "lock", "motion", "networkstatus",
                        "presence", "pressure", "rtt", "status", "switch",
                        "temperature", "wind", "windspeed",
                    }
                    is_weather = "weather" in str(label).lower()
                    states = []
                    for key, value in attributes.items():
                        normalized = str(key).lower().replace("_", "")
                        if (
                            normalized not in common
                            and not (is_weather and len(states) < 16)
                        ):
                            continue
                        rendered = str(value)
                        if len(rendered) > 80:
                            rendered = rendered[:77] + "..."
                        states.append(f"{key}={rendered}")
                        if len(states) >= (16 if is_weather else 10):
                            break
                    rows.append(
                        f"- {label!r} | ID: {device_id} | Room: {room} | "
                        f"Capabilities: {', '.join(map(str, capabilities)) or 'unknown'}"
                        + (f" | Current: {', '.join(states)}" if states else "")
                    )
            except Exception as exc:
                logger.warning("Could not build live device manifest: %s", exc)
        manifest = "\n".join(rows) or "Device manifest omitted or unavailable."
        app_section = ""
        if self._matches(user_prompt, _APP_TERMS):
            apps = await self._cached_app_manifest()
            app_rows = []
            for app in apps:
                app_id = app.get("id") or app.get("appId")
                label = app.get("label") or app.get("name") or app.get("displayName")
                if app_id is not None and label:
                    state = " | ".join(
                        f"{key}: {app[key]}"
                        for key in (
                            "status", "enabled", "paused", "active", "broken",
                        )
                        if app.get(key) is not None
                    )
                    app_rows.append(
                        f"- {label!r} | appId: {app_id}"
                        + (f" | {state}" if state else "")
                    )
            app_section = (
                "\n\nLIVE APP MANIFEST\n"
                + ("\n".join(app_rows) if app_rows else "No live app manifest available.")
                + "\nThis cached manifest is for name-to-ID matching only. For current "
                "automation status, always call hub_read_apps_code with "
                "tool='hub_list_apps' and args={'scope': 'instances'}, and use "
                "hub_read_rules for live Rule Machine rule state. Report enabled, "
                "paused, broken, and active state when returned."
                + "\nPause/resume Rule Machine apps through "
                "hub_manage_native_rules_and_apps with tool='hub_set_rule_paused' "
                "and args={'appId': <id>, 'value': true to pause or false to resume}."
            )
        update_section = ""
        if self._matches(user_prompt, {"firmware", "software", "update", "updates"}):
            update_section = (
                "\n\nUPDATE STATUS RULES\nCall hub_get_info with includeAppUpdate=true. "
                "Compare the current firmware/app versions with every returned update "
                "version and status field. Values such as 'Update Available', "
                "updateAvailable=true, or a newer hubUpdateVersion mean an update is "
                "available; never summarize those values as up to date. Distinguish hub "
                "firmware updates from MCP Server App updates. If the user asks to "
                "install an available Hubitat hub firmware update, first verify that "
                "hub_get_info reports one, then call hub_update_firmware exactly once "
                "with {'confirm': true}. This is a sensitive action and must remain "
                "behind the session confirmation gate. Never claim that an update was "
                "started unless hub_update_firmware succeeds. If it reports that a "
                "backup is required, report that requirement and do not bypass it."
            )
        battery_section = ""
        if self._matches(user_prompt, {"battery", "batteries"}):
            battery_section = (
                "\n\nLOW BATTERY RULE\nA battery is low only when its numeric level "
                "is at or below 20 percent, matching the dashboard. Exclude every device "
                "above 20 percent. Do not reinterpret 30 or 35 percent as low."
            )
        health_section = ""
        if self._matches(user_prompt, _DEVICE_HEALTH_TERMS):
            health_section = (
                "\n\nDEVICE HEALTH RULES\nSeparate results into Offline and Stale "
                "sections. Call a device offline only when Hubitat explicitly reports "
                "healthStatus=offline, networkStatus=offline/unavailable, rtt=timeout, "
                "or a failed health status. Never say no devices are offline when any "
                "of those explicit states is present. Stale means no recent "
                "event (normally over 24 hours) and does not prove a device is offline. "
                "Battery sensors, buttons, remotes, tariff records, and rarely changing "
                "devices may be healthy but stale. Include last activity or stale age "
                "when returned. Prefer explicit health/network/RTT states over age. "
                "When health is absent or ambiguous and a device has HealthCheck/Ping, "
                "you may call hub_manage_devices with tool='hub_call_device_command' "
                "and command='ping' (or 'refresh'), then re-read its status. Ping and "
                "refresh are non-sensitive checks. Limit active checks to five devices "
                "per request and report which devices were not actively checked."
            )
        home_section = ""
        if any(
            re.search(pattern, user_prompt.lower()) is not None
            for pattern in _HOME_STATE_PATTERNS
        ):
            home_section = (
                "\n\nWHOLE-HOME SUMMARY RULES\nGive a compact structured snapshot "
                "covering: people/presence; active motion; lights and notable switches "
                "that are on; open doors/windows and unlocked locks; low batteries at "
                "or below 20 percent; hub/security alerts; and notable climate or weather "
                "conditions when present. Omit empty categories. Do not say the home is "
                "quiet when anyone is present, motion is active, a contact is open, a "
                "light is on, or an alert exists. Distinguish named-person presence from "
                "room presence sensors."
            )
        room_section = ""
        if self._matches(user_prompt, _ROOM_TERMS):
            room_section = (
                "\n\nACTIVE ROOM RULE\nWhen asked which rooms are active, call "
                "homebrain_active_rooms. Active means motion=active or at least one "
                "light in that room has switch=on, exactly matching the dashboard. "
                "Do not filter for a generic active=true device attribute."
            )
        switch_section = ""
        if (
            self._matches(user_prompt, {"switch", "switches"})
            and not self._requests_mutation(user_prompt)
        ):
            switch_section = (
                "\n\nACTIVE SWITCH RULE\nWhen asked which switches are on, call "
                "homebrain_active_switches. It excludes devices with light or bulb "
                "capabilities, exactly matching the dashboard Switches on tile. "
                "Report the returned count and every returned device; do not add lights."
            )
        light_section = ""
        if (
            self._matches(user_prompt, {"light", "lights", "lamp", "lamps"})
            and not self._requests_mutation(user_prompt)
        ):
            light_section = (
                "\n\nACTIVE LIGHT RULE\nWhen asked which lights are on, call "
                "homebrain_active_lights. It returns the exhaustive live list and "
                "count using the same light classification as the dashboard. Do not "
                "scan the device manifest or call a generic device read instead."
            )
        control_section = ""
        if self._requests_mutation(user_prompt):
            control_section = (
                "\n\nROUTINE DEVICE CONTROL\nFor light/switch on, off, toggle, "
                "call homebrain_control_devices once. For a room request pass the "
                "exact room, device_kind, and command; for named devices pass exact "
                "device_names, device_kind, and command. It resolves all targets and "
                "executes and verifies them concurrently. Do not call hub_search_tools "
                "or hub_read_devices before this high-level tool. For setLevel, setColor, or "
                "setColorTemperature, use hub_manage_devices with exact device IDs. "
                "Routine light/switch commands do not require confirmation. Locks, garage "
                "doors, destructive device operations, and security controls remain "
                "sensitive."
            )
        log_section = ""
        if self._matches(user_prompt, _LOG_TERMS):
            log_section = (
                "\n\nLIVE HUB LOG RULES\nYou must fetch actual hub logs before "
                "answering. Call hub_read_diagnostics with tool='hub_get_logs' and "
                "args={'since': '30m', 'limit': 100} unless the user requested another "
                "window, level, source, device, or app. Never infer logs from the device "
                "manifest, events, or prior conversation. State the queried time window "
                "and returned entry count. Count warn and error entries separately, "
                "prioritize them over repetitive info telemetry, and include timestamps "
                "for representative findings. If the tool fails or returns no logs, say "
                "that explicitly rather than constructing a plausible summary."
            )
        return (
            "You are HomeBrainOS, a concise smart-home assistant. The device manifest "
            "is for name and ID resolution only, not proof of current state. For "
            "exhaustive lists, thresholds, counts, or comparisons over any device "
            "attribute, call homebrain_filter_devices and report only its matches and "
            "coverage. Do not scan the manifest yourself. Use Hubitat MCP for every "
            "action. Match informal names against the "
            "manifest and use exact IDs whenever possible. Never invent devices, states, "
            "tool results, or successful actions. Ask one short clarification only when "
            "needed. Sensitive actions are confirmed by the host. This MCP server uses "
            "category gateways: call a gateway with tool='<sub-tool name>' and "
            "args={<sub-tool arguments>}. For device questions, use hub_read_devices "
            "with tool='hub_list_devices' or tool='hub_get_device'; do not call the "
            "gateway with empty arguments.\n\n"
            f"LIVE DEVICE MANIFEST\n{manifest}{app_section}{update_section}"
            f"{battery_section}{health_section}{home_section}{room_section}"
            f"{switch_section}{light_section}{control_section}"
            f"{log_section}"
        )

    @staticmethod
    def _tool_schema(tool: MCPTool) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.name,
                "parameters": tool.input_schema or {"type": "object", "properties": {}},
            },
        }

    @staticmethod
    def _history(history: Any) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for item in list(history or [])[-20:]:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue
            role = "assistant" if item.get("role") in {"assistant", "model"} else "user"
            content = item.get("content") or item.get("text")
            if content:
                messages.append({"role": role, "content": str(content)})
        return messages

    def _result_payload(self, result: MCPToolResult) -> str:
        payload = (
            {"error": result.text or "MCP tool failed"}
            if result.is_error
            else {"result": result.data if result.data is not None else result.text}
        )
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        if len(serialized) <= self.max_tool_result_chars:
            return serialized
        return json.dumps(
            {
                "result_excerpt": serialized[: self.max_tool_result_chars],
                "truncated": True,
                "original_chars": len(serialized),
                "instruction": "Use pagination or a narrower query for more detail.",
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _discovered_tools(
        result: MCPToolResult, available: dict[str, MCPTool]
    ) -> list[MCPTool]:
        if result.is_error:
            return []
        searchable = json.dumps(result.data, ensure_ascii=False, default=str)
        return [
            tool for name, tool in available.items()
            if name != "hub_search_tools"
            and re.search(rf"\b{re.escape(name)}\b", searchable)
        ]

    @staticmethod
    def _is_sensitive(tool: MCPTool, arguments: dict[str, Any]) -> bool:
        annotations = tool.annotations or {}
        if annotations.get("readOnlyHint") is True:
            return False
        name = tool.name.lower().replace("-", "_")
        argument_text = str(arguments).lower().replace("-", "_")
        tokens = set(re.findall(r"[a-z0-9]+", argument_text))
        if name == "hub_manage_devices":
            dangerous = {
                "close", "delete", "factory", "garage", "lock", "open",
                "remove", "replace", "swap", "unlock",
            }
            routine = {
                "off", "on", "ping", "refresh", "setcolor",
                "setcolortemperature", "setlevel", "toggle",
            }
            if tokens & routine and not tokens & dangerous:
                return False
            if tokens & _MUTATION_TERMS:
                return True
            if tokens & _READ_ONLY_TERMS:
                return False
        if annotations.get("destructiveHint") is True:
            return True
        return any(term in f"{name} {argument_text}" for term in _SENSITIVE_TERMS)

    async def _chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Ollama Online API key is not configured")
        if callable(getattr(self.ai_client, "stream", None)):
            return await self._chat_stream(messages, tools)
        started = time.monotonic()
        response = await self.ai_client.post(
            f"{self.base_url}/api/chat",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model_name,
                "messages": messages,
                "tools": tools or None,
                "stream": False,
                "options": {"temperature": 0.1},
            },
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama returned no assistant message")
        logger.info(
            "Ollama round completed in %.3fs with %d declared tools",
            time.monotonic() - started,
            len(tools),
        )
        return message

    async def _chat_stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        started = time.monotonic()
        first_chunk_at: float | None = None
        chunk_count = 0
        content: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        request = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools or None,
            "stream": True,
            "options": {"temperature": 0.1},
        }
        async with self.ai_client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=request,
        ) as response:
            response.raise_for_status()
            lines = response.aiter_lines()
            while True:
                try:
                    line = await asyncio.wait_for(
                        anext(lines), timeout=self.stream_idle_timeout_seconds
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError as exc:
                    elapsed = time.monotonic() - started
                    logger.warning(
                        "Ollama stream stalled after %.3fs and %d chunks",
                        elapsed,
                        chunk_count,
                    )
                    raise TimeoutError(
                        "Ollama stream produced no data for "
                        f"{self.stream_idle_timeout_seconds:g}s "
                        f"after {elapsed:.1f}s and {chunk_count} chunks"
                    ) from exc
                if not line.strip():
                    continue
                chunk_count += 1
                if first_chunk_at is None:
                    first_chunk_at = time.monotonic()
                    logger.info(
                        "Ollama first stream chunk arrived in %.3fs",
                        first_chunk_at - started,
                    )
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Ollama returned invalid streamed JSON") from exc
                if payload.get("error"):
                    raise RuntimeError(str(payload["error"]))
                message = payload.get("message")
                if not isinstance(message, dict):
                    continue
                if message.get("content"):
                    content.append(str(message["content"]))
                calls = message.get("tool_calls")
                if isinstance(calls, list):
                    tool_calls.extend(
                        call for call in calls if isinstance(call, dict)
                    )
        if not content and not tool_calls:
            raise RuntimeError("Ollama returned no assistant message")
        logger.info(
            "Ollama streamed round completed in %.3fs with %d chunks and %d "
            "declared tools",
            time.monotonic() - started,
            chunk_count,
            len(tools),
        )
        message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(content),
        }
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message

    async def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        final_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    "Answer the original request now using only the MCP results already "
                    "provided. Do not request another tool. Be concise and factual."
                ),
            },
        ]
        response = await self._chat(final_messages, [])
        return str(response.get("content") or "The MCP request completed without a written answer.")

    def _take_confirmation(
        self, session_id: str, prompt: str
    ) -> PendingConfirmation | None:
        pending = self._pending.get(session_id)
        if not pending:
            return None
        if pending.expires_at <= time.monotonic():
            self._pending.pop(session_id, None)
            return None
        if " ".join(prompt.strip().lower().split()) not in _CONFIRM_WORDS:
            self._pending.pop(session_id, None)
            return None
        self._pending.pop(session_id, None)
        return pending

    async def _resume_confirmation(
        self, pending: PendingConfirmation, tools: list[dict[str, Any]]
    ) -> str:
        messages = [
            *pending.messages,
            pending.assistant_message,
        ]
        for tool_name, arguments in pending.actions:
            try:
                started = time.monotonic()
                result = await self.mcp.call_tool(tool_name, arguments)
                self._record_evidence(
                    tool_name,
                    arguments,
                    success=self._tool_succeeded(result),
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=self._result_summary(result),
                )
                content = self._result_payload(result)
            except Exception as exc:
                self._record_evidence(
                    tool_name,
                    arguments,
                    success=False,
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                )
                content = json.dumps({"error": str(exc)})
            messages.append(
                {"role": "tool", "tool_name": tool_name, "content": content}
            )
        response = await self._chat(messages, tools)
        return str(response.get("content") or "Confirmed command completed.")

    async def process_user_request_result(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> AgentOutcome:
        request_class = self._classify_request(user_prompt, session_id)
        evidence_token = self._evidence.set([])
        class_token = self._request_class.set(request_class)
        try:
            message = await self._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            return AgentOutcome(
                message=message,
                request_class=request_class,
                evidence=list(self._evidence.get() or []),
            )
        finally:
            self._request_class.reset(class_token)
            self._evidence.reset(evidence_token)

    async def process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        return (
            await self.process_user_request_result(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
        ).message

    async def _process_user_request(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> str:
        request_started = time.monotonic()
        all_tools = (await self.mcp.list_tools())[: self.tool_limit]
        local_filter = self._device_filter_tool()
        local_active_lights = self._active_lights_tool()
        local_active_rooms = self._active_rooms_tool()
        local_active_switches = self._active_switches_tool()
        local_control = self._control_devices_tool()
        local_hub_info = self._hub_info_tool()
        all_tools.extend([
            local_filter, local_active_lights, local_active_rooms,
            local_active_switches, local_control, local_hub_info
        ])
        all_by_name = {tool.name: tool for tool in all_tools}
        pending = self._take_confirmation(session_id, user_prompt)
        if pending:
            pending_names = {name for name, _ in pending.actions}
            declared = [
                tool for tool in all_tools if tool.name in pending_names
            ] or all_tools
        else:
            declared = self._select_tools(user_prompt, all_tools)
            hub_info_request = (
                self._matches(user_prompt, _DIAGNOSTIC_TERMS)
                or bool(
                    re.search(
                        r"\bhub\s+(?:info|information|resources?|status)\b",
                        user_prompt,
                        flags=re.IGNORECASE,
                    )
                )
            )
            if hub_info_request:
                declared = [
                    tool for tool in declared if tool.name != "hub_get_info"
                ]
                if all(
                    tool.name != _LOCAL_HUB_INFO_TOOL for tool in declared
                ):
                    declared.append(local_hub_info)
            if (
                self._request_class.get() == "live-read"
                and all(tool.name != _LOCAL_FILTER_TOOL for tool in declared)
            ):
                declared.append(local_filter)
            if (
                self._matches(user_prompt, {"light", "lights", "lamp", "lamps"})
                and not self._requests_mutation(user_prompt)
                and all(tool.name != _LOCAL_ACTIVE_LIGHTS_TOOL for tool in declared)
            ):
                declared.append(local_active_lights)
            if (
                self._matches(user_prompt, _ROOM_TERMS)
                and all(tool.name != _LOCAL_ACTIVE_ROOMS_TOOL for tool in declared)
            ):
                declared.append(local_active_rooms)
            if (
                self._matches(user_prompt, {"switch", "switches"})
                and not self._requests_mutation(user_prompt)
                and all(tool.name != _LOCAL_ACTIVE_SWITCHES_TOOL for tool in declared)
            ):
                declared.append(local_active_switches)
            if (
                self._requests_mutation(user_prompt)
                and all(tool.name != _LOCAL_CONTROL_TOOL for tool in declared)
            ):
                declared.append(local_control)
        by_name = {tool.name: tool for tool in declared}
        tools = [self._tool_schema(tool) for tool in declared]
        if pending:
            return await self._resume_confirmation(pending, tools)
        prompt_started = time.monotonic()
        system_prompt = await self._system_prompt(user_prompt)
        logger.info(
            "System prompt built in %.3fs (%d chars, manifest=%s)",
            time.monotonic() - prompt_started,
            len(system_prompt),
            self._include_identity_manifest(user_prompt),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            *self._history(conversation_history),
            {"role": "user", "content": str(user_prompt).strip()},
        ]
        completed_calls: set[str] = set()
        mutation_requested = self._requests_mutation(user_prompt)
        logs_requested = self._matches(user_prompt, _LOG_TERMS)
        logs_checked = False
        log_retry_used = False
        successful_mutations = 0
        failed_mutation = ""
        control_retry_used = False
        evidence_retry_used = False
        for _ in range(self.max_tool_rounds):
            assistant = await self._chat(messages, tools)
            calls = assistant.get("tool_calls") or []
            if not calls:
                if logs_requested and not logs_checked:
                    if not log_retry_used:
                        log_retry_used = True
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": (
                                    "Do not answer yet. Fetch the actual logs now by "
                                    "calling hub_read_diagnostics with "
                                    "tool='hub_get_logs' and args={'since':'30m',"
                                    "'limit':100}, then summarize only that result."
                                ),
                            },
                        ])
                        continue
                    return (
                        "I could not retrieve the actual Hubitat logs, so I will not "
                        "provide an inferred log summary."
                    )
                if mutation_requested and successful_mutations == 0:
                    if not control_retry_used:
                        control_retry_used = True
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": (
                                    "You have not executed the requested control. "
                                    "Call the declared Hubitat management tool now "
                                    "using the exact manifest device ID. Do not merely "
                                    "describe the action."
                                ),
                            },
                        ])
                        continue
                    if failed_mutation:
                        return f"The Hubitat action failed: {failed_mutation}"
                    return (
                        "I did not execute a Hubitat control tool, so no device state "
                        "was changed. Please try again with the exact device name."
                    )
                if (
                    self._request_class.get() == "live-read"
                    and not self._has_live_evidence()
                ):
                    if not evidence_retry_used:
                        evidence_retry_used = True
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": (
                                    "Do not answer from memory or inference. No successful "
                                    "live evidence receipt exists yet. Call the most relevant "
                                    "declared Hubitat read tool now, then answer only from its "
                                    "result. Tool discovery alone is not evidence."
                                ),
                            },
                        ])
                        continue
                    return (
                        "I could not retrieve verified live Hubitat evidence, so I will "
                        "not provide an inferred answer."
                    )
                return str(assistant.get("content") or "Done.")
            sensitive: list[tuple[str, dict[str, Any]]] = []
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                arguments = dict(arguments)
                tool = by_name.get(name)
                if (
                    tool
                    and self.require_sensitive_confirmation
                    and self._is_sensitive(tool, arguments)
                ):
                    sensitive.append((name, arguments))
            if sensitive:
                if session_id == "default":
                    return "A unique session_id is required before I can queue a sensitive Hubitat action."
                if len(sensitive) > 12:
                    return "This request proposed more than 12 sensitive actions. Please split it into smaller groups."
                self._pending[session_id] = PendingConfirmation(
                    time.monotonic() + self.confirmation_ttl_seconds,
                    list(sensitive),
                    list(messages),
                    assistant,
                )
                names = sorted({name for name, _ in sensitive})
                if len(sensitive) == 1:
                    if names[0] == "hub_update_firmware":
                        return (
                            "Please confirm before I install the available Hubitat "
                            "firmware update. The hub may restart and be temporarily "
                            "unavailable."
                        )
                    return f"Please confirm before I run the sensitive Hubitat action `{names[0]}`."
                return (
                    f"Please confirm before I run {len(sensitive)} sensitive Hubitat "
                    f"actions through `{', '.join(names)}`."
                )
            messages.append(assistant)
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                signature = json.dumps(
                    [name, arguments], sort_keys=True, ensure_ascii=False, default=str
                )
                if signature in completed_calls:
                    return await self._final_answer(messages)
                completed_calls.add(signature)
                try:
                    tool = by_name.get(name)
                    if not tool:
                        content = json.dumps({"error": f"Undeclared MCP tool: {name}"})
                    else:
                        mcp_started = time.monotonic()
                        if name == _LOCAL_FILTER_TOOL:
                            result = await self._filter_devices(dict(arguments))
                        elif name == _LOCAL_ACTIVE_LIGHTS_TOOL:
                            result = await self._active_lights(dict(arguments))
                        elif name == _LOCAL_ACTIVE_ROOMS_TOOL:
                            result = await self._active_rooms(dict(arguments))
                        elif name == _LOCAL_ACTIVE_SWITCHES_TOOL:
                            result = await self._active_switches(dict(arguments))
                        elif name == _LOCAL_CONTROL_TOOL:
                            result = await self._control_devices(dict(arguments))
                        elif name == _LOCAL_HUB_INFO_TOOL:
                            result = await self._hub_info_snapshot(dict(arguments))
                        else:
                            result = await self.mcp.call_tool(
                                name, dict(arguments)
                            )
                        elapsed_ms = round((time.monotonic() - mcp_started) * 1000)
                        self._record_evidence(
                            name,
                            dict(arguments),
                            success=self._tool_succeeded(result),
                            elapsed_ms=elapsed_ms,
                            summary=self._result_summary(result),
                            supports_live_claim=name != "hub_search_tools",
                            evidence_kind=(
                                "deterministic_attribute_filter"
                                if name == _LOCAL_FILTER_TOOL
                                else (
                                    "deterministic_active_lights"
                                    if name == _LOCAL_ACTIVE_LIGHTS_TOOL
                                    else (
                                        "deterministic_active_rooms"
                                        if name == _LOCAL_ACTIVE_ROOMS_TOOL
                                        else (
                                            "deterministic_active_switches"
                                            if name == _LOCAL_ACTIVE_SWITCHES_TOOL
                                            else (
                                                "deterministic_device_control"
                                                if name == _LOCAL_CONTROL_TOOL
                                                else (
                                                    "authoritative_hub_info_snapshot"
                                                    if name == _LOCAL_HUB_INFO_TOOL
                                                    else "tool_result"
                                                )
                                            )
                                        )
                                    )
                                )
                            ),
                        )
                        if self._is_live_log_call(name, dict(arguments)):
                            logs_checked = self._tool_succeeded(result)
                        logger.info(
                            "MCP tool %s completed in %.3fs",
                            name,
                            time.monotonic() - mcp_started,
                        )
                        content = self._result_payload(result)
                        if name == "hub_search_tools":
                            additions = [
                                item for item in self._discovered_tools(
                                    result, all_by_name
                                )
                                if item.name not in by_name
                            ]
                            if additions:
                                declared.extend(additions)
                                by_name.update({item.name: item for item in additions})
                                tools = [self._tool_schema(item) for item in declared]
                                logger.info(
                                    "Tool search expanded registry with: %s",
                                    ", ".join(item.name for item in additions),
                                )
                        if self._call_is_mutation(tool, dict(arguments)):
                            if self._tool_succeeded(result):
                                successful_mutations += 1
                            else:
                                failed_mutation = result.text or "MCP reported an error"
                        deterministic_message = present_tool_result(
                            name,
                            result.data,
                            failed=not self._tool_succeeded(result),
                            fallback_error=result.text,
                        )
                        if deterministic_message is not None:
                            return deterministic_message
                except Exception as exc:
                    logger.exception("MCP tool %s failed", name)
                    self._record_evidence(
                        name,
                        dict(arguments),
                        success=False,
                        elapsed_ms=round((time.monotonic() - mcp_started) * 1000)
                        if "mcp_started" in locals() else 0,
                        summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                        supports_live_claim=name != "hub_search_tools",
                    )
                    content = json.dumps({"error": str(exc)})
                    if self._call_is_mutation(by_name.get(name), dict(arguments)):
                        failed_mutation = str(exc)
                messages.append({"role": "tool", "tool_name": name, "content": content})
        logger.warning(
            "Agent reached tool-round limit after %.3fs",
            time.monotonic() - request_started,
        )
        return await self._final_answer(messages)


__all__ = ["AgentOutcome", "UnifiedMCPAgent"]
