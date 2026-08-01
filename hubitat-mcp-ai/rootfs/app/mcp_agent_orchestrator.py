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

from agent_prompt_policy import (
    build_system_prompt,
    render_app_manifest,
    render_device_manifest,
)
from deterministic_tool_presenter import present_tool_result
from device_control_service import DeviceControlService
from device_query_service import DeviceQueryService
from device_state_summary import device_attributes
from device_target_resolver import normalized_name
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from request_classification import (
    matches as _matches,
    requests_mutation as _requests_mutation,
    routine_control_arguments as _routine_control_arguments,
)
from tool_registry import (
    EVIDENCE_KINDS as _EVIDENCE_KINDS,
    LOCAL_ACTIVE_LIGHTS_TOOL as _LOCAL_ACTIVE_LIGHTS_TOOL,
    LOCAL_ACTIVE_ROOMS_TOOL as _LOCAL_ACTIVE_ROOMS_TOOL,
    LOCAL_ACTIVE_SWITCHES_TOOL as _LOCAL_ACTIVE_SWITCHES_TOOL,
    LOCAL_CONTROL_TOOL as _LOCAL_CONTROL_TOOL,
    LOCAL_FILTER_TOOL as _LOCAL_FILTER_TOOL,
    LOCAL_HOME_SNAPSHOT_TOOL as _LOCAL_HOME_SNAPSHOT_TOOL,
    LOCAL_HUB_INFO_TOOL as _LOCAL_HUB_INFO_TOOL,
    LOCAL_QUERY_TOOL as _LOCAL_QUERY_TOOL,
    LOCAL_WEATHER_TOOL as _LOCAL_WEATHER_TOOL,
    active_lights_tool as _active_lights_tool,
    active_rooms_tool as _active_rooms_tool,
    active_switches_tool as _active_switches_tool,
    control_devices_tool as _control_devices_tool,
    device_filter_tool as _device_filter_tool,
    device_query_tool as _device_query_tool,
    home_snapshot_tool as _home_snapshot_tool,
    hub_info_tool as _hub_info_tool,
    weather_snapshot_tool as _weather_snapshot_tool,
)

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
_SWITCH_TERMS = {
    "switch", "switches", "which switches", "what switches",
    "switches on", "switches are on",
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
    choices: list[str]


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
        self._choices: ContextVar[list[str] | None] = ContextVar(
            "hubitat_choices", default=None
        )
        self._mutation_call_seen: ContextVar[bool] = ContextVar(
            "hubitat_mutation_call_seen", default=False
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

    async def _routine_control_fallback(
        self,
        prompt: str,
    ) -> str | None:
        arguments = _routine_control_arguments(prompt)
        if arguments is None or _matches(prompt, _SENSITIVE_TERMS):
            return None
        started = time.monotonic()
        result = await self._control_devices(arguments)
        self._record_evidence(
            _LOCAL_CONTROL_TOOL,
            arguments,
            success=self._tool_succeeded(result),
            elapsed_ms=round((time.monotonic() - started) * 1000),
            summary=self._result_summary(result),
            evidence_kind=_EVIDENCE_KINDS[_LOCAL_CONTROL_TOOL],
        )
        if isinstance(result.data, dict) and isinstance(
            result.data.get("choices"), list
        ):
            self._choices.set([
                str(choice)
                for choice in result.data["choices"]
                if str(choice).strip()
            ])
        if (
            not self._tool_succeeded(result)
            and not self._choices.get()
        ):
            return None
        return present_tool_result(
            _LOCAL_CONTROL_TOOL,
            result.data,
            failed=not self._tool_succeeded(result),
            fallback_error=result.text,
        )

    @staticmethod
    def _is_conversational_prompt(prompt: str) -> bool:
        normalized = " ".join(prompt.strip().lower().split())
        conversational = (
            r"(?:hi|hello|hey|thanks|thank you|good morning|good evening)[.!? ]*",
            r"(?:help|what can you do|who are you)[.!? ]*",
        )
        return any(re.fullmatch(pattern, normalized) for pattern in conversational)

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
        mutates: bool = False,
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
            "mutates": bool(mutates),
            "arguments": self._redact(arguments),
            "summary": summary,
        })

    def _has_live_evidence(self) -> bool:
        return any(
            receipt.get("success") and receipt.get("supports_live_claim")
            for receipt in (self._evidence.get() or [])
        )

    _matches = staticmethod(_matches)
    _requests_mutation = staticmethod(_requests_mutation)
    _routine_control_arguments = staticmethod(_routine_control_arguments)

    @staticmethod
    def _device_attributes(device: dict[str, Any]) -> dict[str, Any]:
        return device_attributes(device)

    @staticmethod
    def _device_attribute_units(device: dict[str, Any]) -> dict[str, str]:
        attributes = (
            device.get("attributes")
            or device.get("currentStates")
            or device.get("states")
            or {}
        )
        if not isinstance(attributes, list):
            return {}
        return {
            str(item.get("name")): str(item.get("unit")).strip()
            for item in attributes
            if isinstance(item, dict)
            and item.get("name")
            and item.get("unit") not in {None, ""}
        }

    @staticmethod
    def _inferred_memory_unit(value: Any) -> str | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number >= 100_000:
            return "KB"
        if number >= 16:
            return "MB"
        return "GB"

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

    @classmethod
    def _find_device_record(cls, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        if (
            value.get("id") is not None
            or value.get("deviceId") is not None
        ) and any(
            key in value
            for key in (
                "attributes",
                "currentStates",
                "states",
                "capabilities",
                "commands",
                "label",
                "displayName",
            )
        ):
            return value
        for key in ("device", "result", "data", "output", "content"):
            if key in value:
                candidate = cls._find_device_record(value[key])
                if candidate is not None:
                    return candidate
        return None

    @classmethod
    def _merge_device_identity(
        cls,
        live_devices: list[dict[str, Any]],
        identity_devices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        identities = {
            str(device.get("id") or device.get("deviceId")): device
            for device in identity_devices
            if isinstance(device, dict)
            and (device.get("id") is not None or device.get("deviceId") is not None)
        }
        merged: list[dict[str, Any]] = []
        for live in live_devices:
            device_id = str(live.get("id") or live.get("deviceId") or "")
            identity = identities.get(device_id, {})
            identity_attributes = cls._device_attributes(identity)
            live_attributes = cls._device_attributes(live)
            device = {**identity, **live}
            if identity_attributes or live_attributes:
                device["attributes"] = {
                    **identity_attributes,
                    **live_attributes,
                }
            merged.append(device)
        return merged

    async def _hub_info_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
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
                    for item in (HubitatMCPClient._find_device_list(source.data) or [])
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
        device_id = str(hub_device.get("id") or hub_device.get("deviceId") or "")
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
                    "tool": "hub_get_device",
                    "args": {"deviceId": device_id},
                },
            )
            candidates = [
                item
                for item in (HubitatMCPClient._find_device_list(source.data) or [])
                if isinstance(item, dict)
            ]
            if not candidates:
                candidate = self._find_device_record(source.data)
                if candidate is not None:
                    candidates = [candidate]
            live_device = self._hub_info_device(candidates)
            if live_device is None and len(candidates) == 1:
                live_device = candidates[0]
            if live_device is not None:
                live_device = self._merge_device_identity([live_device], [hub_device])[0]
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
                {"success": False, "error": "Hub Info attributes were unavailable after refresh"},
                is_error=True,
            )
        values = {**live_device, **self._device_attributes(live_device)}
        attribute_units = self._device_attribute_units(live_device)

        def value(*names: str) -> Any:
            return next(
                (
                    values.get(name)
                    for name in names
                    if values.get(name) is not None and values.get(name) != ""
                ),
                None,
            )

        installed = value("firmwareVersionString", "firmwareVersion")
        available = value("hubUpdateVersion")
        update_status = value("hubUpdateStatus")
        update_available = (
            "available" in str(update_status or "").casefold()
            or (bool(installed) and bool(available) and str(installed) != str(available))
        )
        free_memory = value("freeMemory")
        temperature = value("temperatureC", "temperature", "temperatureF")
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
            "free_memory": free_memory,
            "free_memory_unit": attribute_units.get("freeMemory") or self._inferred_memory_unit(free_memory),
            "free_memory_15_min": value("freeMem15"),
            "jvm_free": value("jvmFree"),
            "jvm_size": value("jvmSize"),
            "java_direct": value("javaDirect"),
            "temperature": temperature,
            "temperature_unit": attribute_units.get("temperatureC") or attribute_units.get("temperature") or ("°C" if temperature is not None else None),
            "uptime": value("formattedUptime", "uptime"),
            "database_size": value("dbSize"),
            "database_size_unit": attribute_units.get("dbSize") or "MB",
            "ip_address": value("localIP", "ipAddress"),
            "zigbee_healthy": value("zbHealthy"),
            "zwave_healthy": value("zwHealthy"),
            "hub_alerts": value("hubAlerts"),
            "matter_status": value("matterStatus"),
            "last_poll": value("lastPollTime"),
        }
        return MCPToolResult(_LOCAL_HUB_INFO_TOOL, arguments, {}, json.dumps(data), data)

    async def _filter_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self._record_evidence)
        return await service.filter_devices(arguments)

    async def _query_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self._record_evidence)
        return await service.query_devices(arguments)

    async def _weather_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self._record_evidence)
        return await service.weather_snapshot(arguments)

    @staticmethod
    def _attribute_matches(actual: Any, operator: str, expected: Any) -> bool:
        return DeviceQueryService._attribute_matches(actual, operator, expected)

    async def _active_lights(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self._record_evidence)
        return await service.active_lights(arguments)

    async def _active_rooms(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self._record_evidence)
        return await service.active_rooms(arguments)

    async def _active_switches(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self._record_evidence)
        return await service.active_switches(arguments)

    async def _home_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self._record_evidence)
        return await service.home_snapshot(arguments)

    async def _control_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceControlService(self.mcp, self._record_evidence)
        return await service.execute(arguments)

    @classmethod
    def _needs_device_manifest(cls, prompt: str) -> bool:
        return _matches(prompt, _DEVICE_TERMS) or any(
            re.search(pattern, prompt.lower()) is not None
            for pattern in _HOME_STATE_PATTERNS
        )

    def _include_identity_manifest(self, prompt: str) -> bool:
        tokens = set(re.findall(r"[a-z0-9]+", prompt.casefold()))
        routine_control = (
            _requests_mutation(prompt)
            and bool(tokens & {"on", "off", "toggle"})
            and not bool(tokens & {"garage", "lock", "security", "unlock"})
        )
        return (
            self._needs_device_manifest(prompt)
            and _requests_mutation(prompt)
            and not routine_control
        )

    @classmethod
    def _call_is_mutation(cls, tool: MCPTool | None, arguments: dict[str, Any]) -> bool:
        if not tool:
            return False
        annotations = tool.annotations or {}
        if annotations.get("mutates") is not None:
            return bool(annotations.get("mutates"))
        if annotations.get("readOnlyHint") is True:
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
        return name == "hub_read_diagnostics" and str(arguments.get("tool") or "") == "hub_get_logs"

    @classmethod
    def _select_tools(cls, prompt: str, tools: list[MCPTool]) -> list[MCPTool]:
        names: set[str] | None = None
        if _matches(prompt, _SWITCH_TERMS):
            names = {"homebrain_active_switches", "hub_read_devices"}
        elif _matches(prompt, _DEVICE_HEALTH_TERMS):
            names = {"hub_read_devices", "hub_read_diagnostics", "hub_manage_devices"}
        elif _matches(prompt, _APP_TERMS):
            names = {"hub_read_apps_code", "hub_read_rules", "hub_search_tools"}
            if _requests_mutation(prompt):
                names.update({"hub_manage_native_rules_and_apps", "hub_manage_rule_machine"})
        elif _matches(prompt, _DEVICE_TERMS):
            names = {"hub_read_devices", "hub_get_info"}
            if _requests_mutation(prompt):
                names.add("hub_manage_devices")
        elif _matches(prompt, _ROOM_TERMS):
            names = {"hub_read_rooms", "hub_search_tools"}
            if _requests_mutation(prompt):
                names.add("hub_manage_rooms")
        elif _matches(prompt, _DIAGNOSTIC_TERMS):
            names = {"hub_get_info", "hub_read_diagnostics", "hub_search_tools"}
            if _requests_mutation(prompt):
                names.update({
                    "hub_manage_diagnostics", "hub_manage_logs", "hub_manage_radio",
                    "hub_manage_destructive_ops", "hub_update_firmware",
                })
        elif _requests_mutation(prompt) and not _matches(prompt, _SENSITIVE_TERMS):
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
            self._app_manifest = [item for item in candidates if isinstance(item, dict)]
            self._app_manifest_at = now
        except Exception as exc:
            logger.warning("Could not build app manifest: %s", exc)
        return list(self._app_manifest)

    async def _system_prompt(self, user_prompt: str = "") -> str:
        manifest = "Device manifest omitted or unavailable."
        if self._include_identity_manifest(user_prompt):
            try:
                started = time.monotonic()
                devices = await self.mcp.get_cached_devices()
                self._record_evidence(
                    "hub_read_devices",
                    {"tool": "hub_list_devices", "source": "short_ttl_cache"},
                    success=True,
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=f"{len(devices)} identity records",
                    supports_live_claim=False,
                    evidence_kind="identity_manifest",
                )
                manifest = render_device_manifest(devices)
            except Exception as exc:
                logger.warning("Could not build live device manifest: %s", exc)
        app_section = ""
        if _matches(user_prompt, _APP_TERMS):
            apps = await self._cached_app_manifest()
            app_section = render_app_manifest(apps)
        return build_system_prompt(manifest, app_section)

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
    def _discovered_tools(result: MCPToolResult, available: dict[str, MCPTool]) -> list[MCPTool]:
        if result.is_error:
            return []
        searchable = json.dumps(result.data, ensure_ascii=False, default=str)
        return [
            tool for name, tool in available.items()
            if name != "hub_search_tools" and re.search(rf"\b{re.escape(name)}\b", searchable)
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
            dangerous = {"close", "delete", "factory", "garage", "lock", "open", "remove", "replace", "swap", "unlock"}
            routine = {"off", "on", "ping", "refresh", "setcolor", "setcolortemperature", "setlevel", "toggle"}
            if tokens & routine and not tokens & dangerous:
                return False
            if tokens & _MUTATION_TERMS:
                return True
            if tokens & _READ_ONLY_TERMS:
                return False
        if annotations.get("destructiveHint") is True:
            return True
        return any(term in f"{name} {argument_text}" for term in _SENSITIVE_TERMS)

    async def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
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

    async def _chat_stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
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
                    tool_calls.extend(call for call in calls if isinstance(call, dict))
        if not content and not tool_calls:
            raise RuntimeError("Ollama returned no assistant message")
        logger.info(
            "Ollama streamed round completed in %.3fs with %d chunks and %d declared tools",
            time.monotonic() - started,
            chunk_count,
            len(tools),
        )
        message: dict[str, Any] = {"role": "assistant", "content": "".join(content)}
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

    def _take_confirmation(self, session_id: str, prompt: str) -> PendingConfirmation | None:
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

    async def _resume_confirmation(self, pending: PendingConfirmation, tools: list[dict[str, Any]]) -> str:
        messages = [*pending.messages, pending.assistant_message]
        for tool_name, arguments in pending.actions:
            self._mutation_call_seen.set(True)
            try:
                started = time.monotonic()
                result = await self.mcp.call_tool(tool_name, arguments)
                self._record_evidence(
                    tool_name,
                    arguments,
                    success=self._tool_succeeded(result),
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=self._result_summary(result),
                    mutates=True,
                )
                content = self._result_payload(result)
            except Exception as exc:
                self._record_evidence(
                    tool_name,
                    arguments,
                    success=False,
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                    mutates=True,
                )
                content = json.dumps({"error": str(exc)})
            messages.append({"role": "tool", "tool_name": tool_name, "content": content})
        response = await self._chat(messages, tools)
        return str(response.get("content") or "Confirmed command completed.")

    async def process_user_request_result(
        self,
        user_prompt: str,
        conversation_history: Any = None,
        *,
        session_id: str = "default",
    ) -> AgentOutcome:
        evidence_token = self._evidence.set([])
        choices_token = self._choices.set([])
        mutation_token = self._mutation_call_seen.set(False)
        class_token = self._request_class.set("tool-driven")
        try:
            message = await self._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            evidence = list(self._evidence.get() or [])
            if self._mutation_call_seen.get():
                request_class = "write"
            elif self._is_conversational_prompt(user_prompt) and not evidence:
                request_class = "conversational"
            else:
                request_class = "live-read"
            return AgentOutcome(
                message=message,
                request_class=request_class,
                evidence=evidence,
                choices=list(self._choices.get() or []),
            )
        finally:
            self._request_class.reset(class_token)
            self._mutation_call_seen.reset(mutation_token)
            self._evidence.reset(evidence_token)
            self._choices.reset(choices_token)

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
        local_filter = _device_filter_tool()
        local_query = _device_query_tool()
        local_active_lights = _active_lights_tool()
        local_active_rooms = _active_rooms_tool()
        local_active_switches = _active_switches_tool()
        local_home_snapshot = _home_snapshot_tool()
        local_control = _control_devices_tool()
        local_hub_info = _hub_info_tool()
        local_weather = _weather_snapshot_tool()
        safe_read_tools = [
            local_filter, local_query, local_active_lights, local_active_rooms,
            local_active_switches, local_home_snapshot, local_hub_info, local_weather,
        ]
        all_tools.extend([*safe_read_tools, local_control])
        all_by_name = {tool.name: tool for tool in all_tools}
        pending = self._take_confirmation(session_id, user_prompt)
        if pending:
            pending_names = {name for name, _ in pending.actions}
            declared = [tool for tool in all_tools if tool.name in pending_names] or all_tools
        else:
            declared = self._select_tools(user_prompt, all_tools)
            if (
                not self._is_conversational_prompt(user_prompt)
                and all(tool.name != _LOCAL_CONTROL_TOOL for tool in declared)
            ):
                declared = [tool for tool in declared if tool.name != "hub_get_info"]
                declared_names = {tool.name for tool in declared}
                declared.extend(tool for tool in safe_read_tools if tool.name not in declared_names)
            if (
                _requests_mutation(user_prompt)
                and all(tool.name != _LOCAL_CONTROL_TOOL for tool in declared)
            ):
                declared.append(local_control)
        by_name = {tool.name: tool for tool in declared}
        tools = [self._tool_schema(tool) for tool in declared]
        if pending:
            return await self._resume_confirmation(pending, tools)
        prompt_started = time.monotonic()
        system_prompt = await self._system_prompt(user_prompt)
        if _matches(user_prompt, {"weather"}):
            weather_started = time.monotonic()
            weather_result = await self._weather_snapshot({})
            self._record_evidence(
                _LOCAL_WEATHER_TOOL,
                {},
                success=self._tool_succeeded(weather_result),
                elapsed_ms=round((time.monotonic() - weather_started) * 1000),
                summary=self._result_summary(weather_result),
                evidence_kind=_EVIDENCE_KINDS[_LOCAL_WEATHER_TOOL],
            )
            if self._tool_succeeded(weather_result):
                system_prompt += (
                    "\n\nAUTHORITATIVE CURRENT WEATHER SNAPSHOT\n"
                    + self._result_payload(weather_result)
                    + "\nAnswer weather questions only from this snapshot."
                )
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
        logs_requested = _matches(user_prompt, _LOG_TERMS)
        logs_checked = False
        log_retry_used = False
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
                                    "tool='hub_get_logs' and args={'since':'30m','limit':100}, "
                                    "then summarize only that result."
                                ),
                            },
                        ])
                        continue
                    return "I could not retrieve the actual Hubitat logs, so I will not provide an inferred log summary."
                if not self._is_conversational_prompt(user_prompt) and not self._has_live_evidence():
                    if not evidence_retry_used:
                        evidence_retry_used = True
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": (
                                    "Do not answer from memory or inference. No successful live evidence "
                                    "receipt exists yet. Call the most relevant declared Hubitat read tool "
                                    "now, then answer only from its result. Tool discovery alone is not evidence."
                                ),
                            },
                        ])
                        continue
                    return "I could not retrieve verified live Hubitat evidence, so I will not provide an inferred answer."
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
                if self._call_is_mutation(tool, arguments):
                    self._mutation_call_seen.set(True)
                if tool and self.require_sensitive_confirmation and self._is_sensitive(tool, arguments):
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
                        return "Please confirm before I install the available Hubitat firmware update. The hub may restart and be temporarily unavailable."
                    return f"Please confirm before I run the sensitive Hubitat action `{names[0]}`."
                return f"Please confirm before I run {len(sensitive)} sensitive Hubitat actions through `{', '.join(names)}`."
            messages.append(assistant)
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                signature = json.dumps([name, arguments], sort_keys=True, ensure_ascii=False, default=str)
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
                        elif name == _LOCAL_QUERY_TOOL:
                            result = await self._query_devices(dict(arguments))
                        elif name == _LOCAL_WEATHER_TOOL:
                            result = await self._weather_snapshot(dict(arguments))
                        elif name == _LOCAL_ACTIVE_LIGHTS_TOOL:
                            result = await self._active_lights(dict(arguments))
                        elif name == _LOCAL_ACTIVE_ROOMS_TOOL:
                            result = await self._active_rooms(dict(arguments))
                        elif name == _LOCAL_ACTIVE_SWITCHES_TOOL:
                            result = await self._active_switches(dict(arguments))
                        elif name == _LOCAL_HOME_SNAPSHOT_TOOL:
                            result = await self._home_snapshot(dict(arguments))
                        elif name == _LOCAL_CONTROL_TOOL:
                            result = await self._control_devices(dict(arguments))
                        elif name == _LOCAL_HUB_INFO_TOOL:
                            result = await self._hub_info_snapshot(dict(arguments))
                        else:
                            result = await self.mcp.call_tool(name, dict(arguments))
                        elapsed_ms = round((time.monotonic() - mcp_started) * 1000)
                        mutates = self._call_is_mutation(tool, dict(arguments))
                        if mutates:
                            self._mutation_call_seen.set(True)
                        self._record_evidence(
                            name,
                            dict(arguments),
                            success=self._tool_succeeded(result),
                            elapsed_ms=elapsed_ms,
                            summary=self._result_summary(result),
                            supports_live_claim=name != "hub_search_tools",
                            evidence_kind=_EVIDENCE_KINDS.get(name, "tool_result"),
                            mutates=mutates,
                        )
                        if self._is_live_log_call(name, dict(arguments)):
                            logs_checked = self._tool_succeeded(result)
                        logger.info("MCP tool %s completed in %.3fs", name, time.monotonic() - mcp_started)
                        content = self._result_payload(result)
                        if name == "hub_search_tools":
                            additions = [
                                item for item in self._discovered_tools(result, all_by_name)
                                if item.name not in by_name
                            ]
                            if additions:
                                declared.extend(additions)
                                by_name.update({item.name: item for item in additions})
                                tools = [self._tool_schema(item) for item in declared]
                                logger.info("Tool search expanded registry with: %s", ", ".join(item.name for item in additions))
                        deterministic_message = present_tool_result(
                            name,
                            result.data,
                            failed=not self._tool_succeeded(result),
                            fallback_error=result.text,
                        )
                        if (
                            name == _LOCAL_CONTROL_TOOL
                            and isinstance(result.data, dict)
                            and isinstance(result.data.get("choices"), list)
                        ):
                            self._choices.set([
                                str(choice)
                                for choice in result.data["choices"]
                                if str(choice).strip()
                            ])
                        direct_home_snapshot = (
                            name == _LOCAL_HOME_SNAPSHOT_TOOL
                            and any(
                                re.search(pattern, user_prompt.casefold()) is not None
                                for pattern in _HOME_STATE_PATTERNS
                            )
                        )
                        if deterministic_message is not None and (
                            (
                                name not in {_LOCAL_QUERY_TOOL, _LOCAL_HOME_SNAPSHOT_TOOL, _LOCAL_WEATHER_TOOL}
                                or direct_home_snapshot
                            )
                            or not self._tool_succeeded(result)
                        ):
                            return deterministic_message
                except Exception as exc:
                    logger.exception("MCP tool %s failed", name)
                    self._record_evidence(
                        name,
                        dict(arguments),
                        success=False,
                        elapsed_ms=round((time.monotonic() - mcp_started) * 1000) if "mcp_started" in locals() else 0,
                        summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                        supports_live_claim=name != "hub_search_tools",
                        mutates=self._call_is_mutation(by_name.get(name), dict(arguments)),
                    )
                    content = json.dumps({"error": str(exc)})
                messages.append({"role": "tool", "tool_name": name, "content": content})
        logger.warning("Agent reached tool-round limit after %.3fs", time.monotonic() - request_started)
        return await self._final_answer(messages)


__all__ = ["AgentOutcome", "UnifiedMCPAgent"]
