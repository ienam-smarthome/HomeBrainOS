from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from agent_prompt_policy import (
    build_system_prompt,
    render_app_manifest,
    render_device_manifest,
)
from chat_transport import ChatTransport
from confirmation_store import ConfirmationStore, PendingConfirmation
from deterministic_tool_presenter import present_tool_result
from device_control_service import DeviceControlService
from device_query_service import DeviceQueryService
from device_state_summary import device_attributes
from device_target_resolver import normalized_name
from evidence_recorder import EvidenceRecorder
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
    ToolEffect,
    classify_tool_effect,
)

logger = logging.getLogger("HomeBrainOS.Orchestrator")

_SENSITIVE_TERMS = {
    "backup", "delete", "disable", "enable", "factory_reset", "firmware",
    "garage", "lock", "reboot", "restart", "rule", "security", "shutdown", "unlock",
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
_LOG_TERMS = {"log", "logs"}
_HOME_STATE_PATTERNS = (
    r"\bwhat(?:'s| is) happening\b",
    r"\bhome (?:status|summary|overview)\b",
)

_INITIAL_TOOL_ORDER = (
    "hub_search_tools",
    "hub_read_diagnostics",
    _LOCAL_FILTER_TOOL,
    _LOCAL_QUERY_TOOL,
    _LOCAL_ACTIVE_LIGHTS_TOOL,
    _LOCAL_ACTIVE_ROOMS_TOOL,
    _LOCAL_ACTIVE_SWITCHES_TOOL,
    _LOCAL_HOME_SNAPSHOT_TOOL,
    _LOCAL_HUB_INFO_TOOL,
    _LOCAL_WEATHER_TOOL,
    _LOCAL_CONTROL_TOOL,
)


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
        max_history_messages: int = 8,
        max_history_chars: int = 12000,
        max_tool_context_chars: int = 48000,
        compacted_tool_result_chars: int = 1200,
        ai_client: Any | None = None,
    ) -> None:
        self.mcp = mcp_client
        self.transport = ChatTransport(
            api_key,
            model_name,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            stream_idle_timeout_seconds=stream_idle_timeout_seconds,
            client=ai_client,
        )
        self.tool_limit = max(1, int(tool_limit))
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.require_sensitive_confirmation = bool(require_sensitive_confirmation)
        self.confirmations = ConfirmationStore(confirmation_ttl_seconds)
        self.max_tool_result_chars = max(2000, int(max_tool_result_chars))
        self.max_history_messages = max(0, int(max_history_messages))
        self.max_history_chars = max(0, int(max_history_chars))
        self.max_tool_context_chars = max(4000, int(max_tool_context_chars))
        self.compacted_tool_result_chars = max(
            256,
            min(
                int(compacted_tool_result_chars),
                self.max_tool_context_chars // 2,
            ),
        )
        self._app_manifest: list[dict[str, Any]] = []
        self._app_manifest_at = 0.0
        self.evidence = EvidenceRecorder()
        self._request_class: ContextVar[str] = ContextVar(
            "hubitat_request_class", default="live-read"
        )
        self._choices: ContextVar[list[str] | None] = ContextVar(
            "hubitat_choices", default=None
        )
        self._mutation_call_seen: ContextVar[bool] = ContextVar(
            "hubitat_mutation_call_seen", default=False
        )
    @property
    def configured(self) -> bool:
        return self.transport.configured

    @property
    def confirmation_ttl_seconds(self) -> float:
        return self.confirmations.ttl_seconds

    @property
    def _pending(self) -> dict[str, PendingConfirmation]:
        return self.confirmations.pending

    @property
    def api_key(self) -> str:
        return self.transport.api_key

    @property
    def model_name(self) -> str:
        return self.transport.model_name

    @property
    def base_url(self) -> str:
        return self.transport.base_url

    @property
    def timeout_seconds(self) -> float:
        return self.transport.timeout_seconds

    @property
    def ai_client(self) -> Any:
        return self.transport.client

    @property
    def stream_idle_timeout_seconds(self) -> float:
        return self.transport.stream_idle_timeout_seconds

    @stream_idle_timeout_seconds.setter
    def stream_idle_timeout_seconds(self, value: float) -> None:
        self.transport.stream_idle_timeout_seconds = max(0.001, float(value))

    async def close(self) -> None:
        await self.transport.close()

    async def _routine_control_fallback(
        self,
        prompt: str,
    ) -> str | None:
        arguments = _routine_control_arguments(prompt)
        if arguments is None or _matches(prompt, _SENSITIVE_TERMS):
            return None
        started = time.monotonic()
        result = await self._control_devices(arguments)
        self.evidence.record(
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
        mutates: bool | None = None,
        effect: ToolEffect | str | None = None,
    ) -> None:
        self.evidence.record(
            gateway,
            arguments,
            success=success,
            elapsed_ms=elapsed_ms,
            summary=summary,
            supports_live_claim=supports_live_claim,
            evidence_kind=evidence_kind,
            mutates=mutates,
            effect=effect,
        )

    def _has_live_evidence(self) -> bool:
        return self.evidence.has_live_evidence()

    @property
    def _evidence(self) -> ContextVar[list[dict[str, Any]] | None]:
        """Compatibility view; new code should use ``self.evidence``."""

        return self.evidence.context

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
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.filter_devices(arguments)

    async def _query_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.query_devices(arguments)

    async def _weather_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.weather_snapshot(arguments)

    @staticmethod
    def _attribute_matches(actual: Any, operator: str, expected: Any) -> bool:
        return DeviceQueryService._attribute_matches(actual, operator, expected)

    async def _active_lights(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.active_lights(arguments)

    async def _active_rooms(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.active_rooms(arguments)

    async def _active_switches(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.active_switches(arguments)

    async def _home_snapshot(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.home_snapshot(arguments)

    async def _control_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceControlService(self.mcp, self.evidence.record)
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

    @staticmethod
    def _initial_tools(tools: list[MCPTool]) -> list[MCPTool]:
        """Return a stable lean registry without inspecting the user prompt."""

        by_name = {tool.name: tool for tool in tools}
        return [
            by_name[name]
            for name in _INITIAL_TOOL_ORDER
            if name in by_name
        ]

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
            self.evidence.record(
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
                self.evidence.record(
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

    def _history(self, history: Any) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for item in list(history or []):
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue
            role = "assistant" if item.get("role") in {"assistant", "model"} else "user"
            content = item.get("content") or item.get("text")
            if content:
                messages.append({"role": role, "content": str(content)})
        if not self.max_history_messages or not self.max_history_chars:
            return []

        bounded: list[dict[str, Any]] = []
        remaining = self.max_history_chars
        for message in reversed(messages[-self.max_history_messages:]):
            content = str(message["content"])
            if remaining <= 0:
                break
            if len(content) > remaining:
                marker = "\n[earlier history truncated]"
                if remaining <= len(marker):
                    break
                keep = max(0, remaining - len(marker))
                content = content[:keep] + (marker if keep else "")
            bounded.append({**message, "content": content})
            remaining -= len(content)
        return list(reversed(bounded))

    @staticmethod
    def _compact_tool_content(content: str, max_chars: int) -> str:
        if max_chars <= 0:
            return ""
        if max_chars < 160:
            return "[older tool result compacted]"[:max_chars]
        payload = {
            "context_compacted": True,
            "original_chars": len(content),
            "result_excerpt": "",
            "instruction": "Use the newer tool results for current detail.",
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        excerpt_chars = max(0, max_chars - len(serialized))
        payload["result_excerpt"] = content[:excerpt_chars]
        serialized = json.dumps(payload, ensure_ascii=False)
        while len(serialized) > max_chars and payload["result_excerpt"]:
            overflow = len(serialized) - max_chars
            payload["result_excerpt"] = payload["result_excerpt"][:-overflow]
            serialized = json.dumps(payload, ensure_ascii=False)
        return serialized[:max_chars]

    def _bounded_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        bounded = [dict(message) for message in messages]
        tool_indices = [
            index for index, message in enumerate(bounded)
            if message.get("role") == "tool" and message.get("content") is not None
        ]
        total = sum(len(str(bounded[index]["content"])) for index in tool_indices)
        original_total = total
        for index in tool_indices:
            if total <= self.max_tool_context_chars:
                break
            content = str(bounded[index]["content"])
            excess = total - self.max_tool_context_chars
            target = max(
                self.compacted_tool_result_chars,
                len(content) - excess,
            )
            if target >= len(content):
                continue
            replacement = self._compact_tool_content(content, target)
            bounded[index]["content"] = replacement
            total += len(replacement) - len(content)
        for index in tool_indices:
            if total <= self.max_tool_context_chars:
                break
            content = str(bounded[index]["content"])
            excess = total - self.max_tool_context_chars
            target = max(0, len(content) - excess)
            replacement = self._compact_tool_content(content, target)
            bounded[index]["content"] = replacement
            total += len(replacement) - len(content)
        if total < original_total:
            logger.info(
                "Compacted retained tool context from %d to %d chars",
                original_total,
                total,
            )
        return bounded

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

        named: set[str] = set()

        def collect(value: Any) -> None:
            if isinstance(value, str):
                if value in available:
                    named.add(value)
                return
            if isinstance(value, dict):
                for item in value.values():
                    collect(item)
                return
            if isinstance(value, list):
                for item in value:
                    collect(item)

        collect(result.data)
        return [
            tool for name, tool in available.items()
            if name != "hub_search_tools" and name in named
        ]

    async def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        return await self.transport.chat(self._bounded_messages(messages), tools)

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
        return self.confirmations.consume(session_id, prompt)

    async def _resume_confirmation(self, pending: PendingConfirmation, tools: list[dict[str, Any]]) -> str:
        messages = [*pending.messages, pending.assistant_message]
        for tool_name, arguments in pending.actions:
            self._mutation_call_seen.set(True)
            effect = classify_tool_effect(
                MCPTool(tool_name, tool_name, {}), arguments
            )
            try:
                started = time.monotonic()
                result = await self.mcp.call_tool(tool_name, arguments)
                self.evidence.record(
                    tool_name,
                    arguments,
                    success=self._tool_succeeded(result),
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=self._result_summary(result),
                    mutates=True,
                    effect=effect,
                )
                content = self._result_payload(result)
            except Exception as exc:
                self.evidence.record(
                    tool_name,
                    arguments,
                    success=False,
                    elapsed_ms=round((time.monotonic() - started) * 1000),
                    summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                    mutates=True,
                    effect=effect,
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
        evidence_token = self.evidence.begin()
        choices_token = self._choices.set([])
        mutation_token = self._mutation_call_seen.set(False)
        class_token = self._request_class.set("tool-driven")
        try:
            message = await self._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            evidence = self.evidence.receipts()
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
            self.evidence.reset(evidence_token)
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
            declared = self._initial_tools(all_tools)
        by_name = {tool.name: tool for tool in declared}
        tools = [self._tool_schema(tool) for tool in declared]
        if pending:
            return await self._resume_confirmation(pending, tools)
        prompt_started = time.monotonic()
        system_prompt = await self._system_prompt(user_prompt)
        if _matches(user_prompt, {"weather"}):
            weather_started = time.monotonic()
            weather_result = await self._weather_snapshot({})
            self.evidence.record(
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
                if (
                    not self._is_conversational_prompt(user_prompt)
                    and not self.evidence.has_live_evidence()
                ):
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
                effect = classify_tool_effect(tool, arguments)
                if effect.mutates:
                    self._mutation_call_seen.set(True)
                if (
                    tool
                    and self.require_sensitive_confirmation
                    and effect.requires_confirmation
                ):
                    sensitive.append((name, arguments))
            if sensitive:
                if not str(session_id).strip() or session_id == "default":
                    return "A unique session_id is required before I can queue a sensitive Hubitat action."
                if len(sensitive) > 12:
                    return "This request proposed more than 12 sensitive actions. Please split it into smaller groups."
                self.confirmations.queue(
                    session_id,
                    sensitive,
                    messages,
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
                        effect = classify_tool_effect(tool, dict(arguments))
                        if effect.mutates:
                            self._mutation_call_seen.set(True)
                        self.evidence.record(
                            name,
                            dict(arguments),
                            success=self._tool_succeeded(result),
                            elapsed_ms=elapsed_ms,
                            summary=self._result_summary(result),
                            supports_live_claim=name != "hub_search_tools",
                            evidence_kind=_EVIDENCE_KINDS.get(name, "tool_result"),
                            mutates=effect.mutates,
                            effect=effect,
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
                    self.evidence.record(
                        name,
                        dict(arguments),
                        success=False,
                        elapsed_ms=round((time.monotonic() - mcp_started) * 1000) if "mcp_started" in locals() else 0,
                        summary=f"{type(exc).__name__}: {str(exc)[:140]}",
                        supports_live_claim=name != "hub_search_tools",
                        effect=classify_tool_effect(
                            by_name.get(name), dict(arguments)
                        ),
                    )
                    content = json.dumps({"error": str(exc)})
                messages.append({"role": "tool", "tool_name": name, "content": content})
        logger.warning("Agent reached tool-round limit after %.3fs", time.monotonic() - request_started)
        return await self._final_answer(messages)


__all__ = ["AgentOutcome", "UnifiedMCPAgent"]
