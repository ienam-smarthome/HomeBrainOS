from __future__ import annotations

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
from confirmation_policy import ConfirmationAction, ConfirmationPolicy
from confirmation_store import CONFIRM_WORDS, ConfirmationStore, PendingConfirmation
from capability_grounding import CapabilityAction, CapabilityGroundingPolicy
from deterministic_tool_presenter import present_tool_result
from device_control_service import DeviceControlService
from device_history_service import DeviceHistoryService
from device_query_service import DeviceQueryService
from evidence_recorder import EvidenceRecorder
from grounding_policy import GroundingAction, GroundingPolicy
from hub_info_service import HubInfoService
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from model_context_policy import ModelContextPolicy
from request_classification import (
    matches as _matches,
    requests_mutation as _requests_mutation,
    routine_control_arguments as _routine_control_arguments,
)
from rule_authoring_service import RuleAuthoringService
from tool_executor import ToolExecutor
from tool_discovery_catalog import SEARCH_TOOL, ToolDiscoveryCatalog
from tool_registry import (
    EVIDENCE_KINDS as _EVIDENCE_KINDS,
    LOCAL_ACTIVE_LIGHTS_TOOL as _LOCAL_ACTIVE_LIGHTS_TOOL,
    LOCAL_ACTIVE_ROOMS_TOOL as _LOCAL_ACTIVE_ROOMS_TOOL,
    LOCAL_ACTIVE_SWITCHES_TOOL as _LOCAL_ACTIVE_SWITCHES_TOOL,
    LOCAL_CONTROL_TOOL as _LOCAL_CONTROL_TOOL,
    LOCAL_DEVICE_HISTORY_TOOL as _LOCAL_DEVICE_HISTORY_TOOL,
    LOCAL_FILTER_TOOL as _LOCAL_FILTER_TOOL,
    LOCAL_HOME_SNAPSHOT_TOOL as _LOCAL_HOME_SNAPSHOT_TOOL,
    LOCAL_HUB_INFO_TOOL as _LOCAL_HUB_INFO_TOOL,
    LOCAL_QUERY_TOOL as _LOCAL_QUERY_TOOL,
    LOCAL_RESOLVE_TOOL as _LOCAL_RESOLVE_TOOL,
    LOCAL_WEATHER_TOOL as _LOCAL_WEATHER_TOOL,
    active_lights_tool as _active_lights_tool,
    active_rooms_tool as _active_rooms_tool,
    active_switches_tool as _active_switches_tool,
    control_devices_tool as _control_devices_tool,
    device_history_tool as _device_history_tool,
    device_filter_tool as _device_filter_tool,
    device_query_tool as _device_query_tool,
    device_resolver_tool as _device_resolver_tool,
    home_snapshot_tool as _home_snapshot_tool,
    hub_info_tool as _hub_info_tool,
    weather_snapshot_tool as _weather_snapshot_tool,
    ToolEffect,
    classify_tool_effect,
    rule_machine_proposal_error,
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

@dataclass(slots=True)
class AgentOutcome:
    message: str
    request_class: str
    evidence: list[dict[str, Any]]
    choices: list[str]
    confirmation_required: bool = False
    confirmation_count: int = 0


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
        self.confirmation_policy = ConfirmationPolicy(
            enabled=self.require_sensitive_confirmation
        )
        self.confirmations = ConfirmationStore(confirmation_ttl_seconds)
        self.max_tool_result_chars = max(2000, int(max_tool_result_chars))
        self.context_policy = ModelContextPolicy(
            max_history_messages=max_history_messages,
            max_history_chars=max_history_chars,
            max_tool_context_chars=max_tool_context_chars,
            compacted_tool_result_chars=compacted_tool_result_chars,
        )
        # Compatibility views for callers that inspect the established agent
        # configuration surface. Context behavior lives in ModelContextPolicy.
        self.max_history_messages = self.context_policy.max_history_messages
        self.max_history_chars = self.context_policy.max_history_chars
        self.max_tool_context_chars = self.context_policy.max_tool_context_chars
        self.compacted_tool_result_chars = (
            self.context_policy.compacted_tool_result_chars
        )
        self._app_manifest: list[dict[str, Any]] = []
        self._app_manifest_at = 0.0
        self.evidence = EvidenceRecorder()
        self.rule_authoring = RuleAuthoringService(
            self.mcp,
            self.evidence.record,
        )
        self.device_history = DeviceHistoryService(
            self.mcp,
            self.evidence.record,
        )
        self.executor = ToolExecutor(
            self.mcp,
            self.evidence,
            local_handlers={
                _LOCAL_FILTER_TOOL: self._filter_devices,
                _LOCAL_QUERY_TOOL: self._query_devices,
                _LOCAL_RESOLVE_TOOL: self._resolve_device,
                _LOCAL_DEVICE_HISTORY_TOOL: self.device_history.history,
                _LOCAL_WEATHER_TOOL: self._weather_snapshot,
                _LOCAL_ACTIVE_LIGHTS_TOOL: self._active_lights,
                _LOCAL_ACTIVE_ROOMS_TOOL: self._active_rooms,
                _LOCAL_ACTIVE_SWITCHES_TOOL: self._active_switches,
                _LOCAL_HOME_SNAPSHOT_TOOL: self._home_snapshot,
                _LOCAL_CONTROL_TOOL: self._control_devices,
                _LOCAL_HUB_INFO_TOOL: self._hub_info_snapshot,
            },
            max_tool_result_chars=self.max_tool_result_chars,
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
        return ToolExecutor.result_summary(result)

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
        return HubInfoService.device_attributes(device)

    @staticmethod
    def _device_attribute_units(device: dict[str, Any]) -> dict[str, str]:
        return HubInfoService.device_attribute_units(device)

    @staticmethod
    def _inferred_memory_unit(value: Any) -> str | None:
        return HubInfoService.inferred_memory_unit(value)

    @staticmethod
    def _hub_info_device(
        devices: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        return HubInfoService.hub_info_device(devices)

    @staticmethod
    def _find_device_record(value: Any) -> dict[str, Any] | None:
        return HubInfoService.find_device_record(value)

    @staticmethod
    def _merge_device_identity(
        live_devices: list[dict[str, Any]],
        identity_devices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return HubInfoService.merge_device_identity(
            live_devices,
            identity_devices,
        )

    async def _hub_info_snapshot(
        self,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        return await HubInfoService(self.mcp).snapshot(arguments)
    async def _filter_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.filter_devices(arguments)

    async def _query_devices(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.query_devices(arguments)

    async def _resolve_device(self, arguments: dict[str, Any]) -> MCPToolResult:
        service = DeviceQueryService(self.mcp, self.evidence.record)
        return await service.resolve_device(arguments)

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
        return ToolExecutor.succeeded(result)

    @staticmethod
    def _is_live_log_call(name: str, arguments: dict[str, Any]) -> bool:
        return GroundingPolicy.is_live_log_call(name, arguments)

    @staticmethod
    def _initial_tools(tools: list[MCPTool]) -> list[MCPTool]:
        """Return a stable lean registry without inspecting the user prompt."""

        return ToolDiscoveryCatalog.initial_tools(tools)

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
        return ToolDiscoveryCatalog.tool_schema(tool)

    def _history(self, history: Any) -> list[dict[str, Any]]:
        return self.context_policy.history(history)

    @staticmethod
    def _compact_tool_content(content: str, max_chars: int) -> str:
        return ModelContextPolicy.compact_tool_content(content, max_chars)

    def _bounded_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return self.context_policy.bounded_messages(messages)

    def _result_payload(self, result: MCPToolResult) -> str:
        return self.executor.result_payload(result)

    @staticmethod
    def _discovered_tools(result: MCPToolResult, available: dict[str, MCPTool]) -> list[MCPTool]:
        return ToolDiscoveryCatalog.discovered_tools(result, available)

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

    @staticmethod
    def _rule_result_data(execution: Any) -> dict[str, Any]:
        data = execution.result.data if execution.result is not None else None
        while isinstance(data, dict):
            if any(
                key in data
                for key in ("success", "appId", "ruleId", "error", "partial", "health")
            ):
                break
            nested = next(
                (
                    data[key]
                    for key in ("result", "data", "output")
                    if isinstance(data.get(key), dict)
                ),
                None,
            )
            if nested is None:
                break
            data = nested
        return data if isinstance(data, dict) else {}

    @classmethod
    def _verified_rule_execution(cls, execution: Any) -> bool:
        data = cls._rule_result_data(execution)
        health = data.get("health") if isinstance(data.get("health"), dict) else {}
        return (
            execution.success
            and data.get("success") is True
            and (data.get("appId") or data.get("ruleId")) not in {None, ""}
            and data.get("partial") is not True
            and health.get("ok") is True
        )

    @staticmethod
    def _queued_rule_name(arguments: dict[str, Any]) -> str:
        payload = arguments.get("args")
        if not isinstance(payload, dict):
            return "Rule Machine rule"
        envelope = payload.get("args")
        source = envelope if isinstance(envelope, dict) else payload
        return str(source.get("name") or "Rule Machine rule")

    def _confirmed_rule_report(
        self,
        outcomes: list[tuple[str, dict[str, Any], Any]],
        *,
        queued_count: int,
    ) -> str | None:
        if not outcomes or any(
            name != "hub_manage_rule_machine" for name, _, _ in outcomes
        ):
            return None
        lines: list[str] = []
        failed = False
        for _, arguments, execution in outcomes:
            name = self._queued_rule_name(arguments)
            data = self._rule_result_data(execution)
            app_id = data.get("appId") or data.get("ruleId")
            if self._verified_rule_execution(execution):
                lines.append(
                    f"- Created **{name}** (appId: {app_id}) and the hub "
                    "reported it healthy."
                )
                continue
            failed = True
            detail = (
                data.get("error")
                or data.get("note")
                or (
                    str(execution.error)
                    if execution.error is not None
                    else "the hub did not return a verified rule ID and healthy result"
                )
            )
            lines.append(f"- **{name} was not verified:** {detail}.")
        skipped = max(0, queued_count - len(outcomes))
        if skipped:
            failed = True
            lines.append(
                f"- {skipped} remaining confirmed action"
                f"{' was' if skipped == 1 else 's were'} not attempted after "
                "the first unverified write."
            )
        heading = (
            "The confirmed Rule Machine write was not fully completed."
            if failed
            else "Confirmed Rule Machine actions completed:"
        )
        return heading + "\n\n" + "\n".join(lines)

    async def _resume_confirmation(self, pending: PendingConfirmation, catalog: ToolDiscoveryCatalog) -> str:
        messages = [*pending.messages, pending.assistant_message]
        outcomes: list[tuple[str, dict[str, Any], Any]] = []
        for tool_name, arguments in pending.actions:
            self._mutation_call_seen.set(True)
            proposal_error = rule_machine_proposal_error(tool_name, arguments)
            if proposal_error is not None:
                return (
                    "The queued Rule Machine action was cancelled because its "
                    f"payload is incomplete. {proposal_error}"
                )
            tool = catalog.available_tool(tool_name)
            approved_arguments = self.confirmation_policy.approved_arguments(
                tool_name,
                arguments,
                tool_schema=tool.input_schema if tool is not None else None,
            )
            execution = await self.executor.execute(
                tool_name,
                approved_arguments,
                tool=tool or MCPTool(tool_name, tool_name, {}),
                mutates=True,
            )
            outcomes.append((tool_name, approved_arguments, execution))
            messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": execution.content,
            })
            if tool_name == "hub_manage_rule_machine":
                if not self._verified_rule_execution(execution):
                    break
        deterministic_report = self._confirmed_rule_report(
            outcomes,
            queued_count=len(pending.actions),
        )
        if deterministic_report is not None:
            return deterministic_report
        response = await self._chat(messages, catalog.schemas())
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
            pending = self.confirmations.pending.get(str(session_id))
            return AgentOutcome(
                message=message,
                request_class=request_class,
                evidence=evidence,
                choices=list(self._choices.get() or []),
                confirmation_required=pending is not None,
                confirmation_count=len(pending.actions) if pending is not None else 0,
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
        local_resolver = _device_resolver_tool()
        local_device_history = _device_history_tool()
        local_active_lights = _active_lights_tool()
        local_active_rooms = _active_rooms_tool()
        local_active_switches = _active_switches_tool()
        local_home_snapshot = _home_snapshot_tool()
        local_control = _control_devices_tool()
        local_hub_info = _hub_info_tool()
        local_weather = _weather_snapshot_tool()
        safe_read_tools = [
            local_filter, local_query, local_resolver, local_device_history,
            local_active_lights, local_active_rooms,
            local_active_switches, local_home_snapshot, local_hub_info, local_weather,
        ]
        all_tools.extend([*safe_read_tools, local_control])
        catalog = ToolDiscoveryCatalog(all_tools)
        pending = self._take_confirmation(session_id, user_prompt)
        if pending:
            pending_names = list(dict.fromkeys(name for name, _ in pending.actions))
            missing = catalog.replace_declared(pending_names)
            if missing:
                return self.confirmation_policy.unavailable_tools_message(missing)
        if pending:
            return await self._resume_confirmation(pending, catalog)
        normalized_prompt = " ".join(str(user_prompt).strip().casefold().split())
        if normalized_prompt in CONFIRM_WORDS:
            return (
                "No Hubitat action is pending confirmation in this browser session. "
                "Nothing was executed. Submit the original request again and only "
                "confirm when the response carries a verified pending action."
            )
        capability_discovery = ""
        capability_additions: list[MCPTool] = []
        search_tool = catalog.declared_tool(SEARCH_TOOL)
        if (
            search_tool is not None
            and not self._is_conversational_prompt(user_prompt)
        ):
            discovery = await self.executor.execute(
                SEARCH_TOOL,
                {"query": str(user_prompt).strip()},
                tool=search_tool,
                supports_live_claim=False,
                record_evidence=False,
            )
            capability_additions = (
                catalog.expand(discovery.result)
                if discovery.result is not None
                else []
            )
            capability_discovery = discovery.content
            if capability_additions:
                logger.info(
                    "Original-request discovery expanded registry with: %s",
                    ", ".join(item.name for item in capability_additions),
                )
        rule_decision = await self.rule_authoring.propose(
            user_prompt,
            available_gateways=set(catalog.declared_names),
            can_read_rules="hub_read_rules" in catalog.available_names,
        )
        if rule_decision.handled:
            if rule_decision.message is not None:
                return rule_decision.message
            sensitive = [
                ("hub_manage_rule_machine", dict(arguments))
                for arguments in rule_decision.actions
            ]
            self._mutation_call_seen.set(bool(sensitive))
            decision = self.confirmation_policy.decide(session_id, sensitive)
            if decision.action is ConfirmationAction.REJECT:
                return str(decision.message)
            assistant_message = {
                "role": "assistant",
                "content": str(decision.message),
                "tool_calls": [
                    {
                        "function": {
                            "name": name,
                            "arguments": arguments,
                        }
                    }
                    for name, arguments in sensitive
                ],
            }
            self.confirmations.queue(
                session_id,
                sensitive,
                [{"role": "user", "content": str(user_prompt).strip()}],
                assistant_message,
            )
            return str(decision.message)
        tools = catalog.schemas()
        prompt_started = time.monotonic()
        system_prompt = await self._system_prompt(user_prompt)
        if capability_discovery:
            system_prompt += (
                "\n\nHOST ORIGINAL-REQUEST CAPABILITY DISCOVERY\n"
                + capability_discovery
                + "\nRelevant returned gateways are already declared. Complete the "
                "user's requested operation; do not replace a create/edit request "
                "with a report that the target does not yet exist."
            )
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
        grounding = GroundingPolicy(
            logs_requested=_matches(user_prompt, _LOG_TERMS),
            conversational=self._is_conversational_prompt(user_prompt),
        )
        capability_grounding = CapabilityGroundingPolicy()
        post_filter_discovery_used = False
        ungrounded_confirmation_claim_seen = False
        for _ in range(self.max_tool_rounds):
            assistant = await self._chat(messages, tools)
            calls = assistant.get("tool_calls") or []
            if not calls:
                answer = str(assistant.get("content") or "")
                resolver_used = any(
                    json.loads(signature)[0] == _LOCAL_RESOLVE_TOOL
                    for signature in completed_calls
                )
                if (
                    re.search(
                        r"\b(?:could not|couldn't|cannot|can't|still cannot|still can't)\s+find\b",
                        answer,
                        re.I,
                    )
                    and not resolver_used
                ):
                    messages.extend([
                        assistant,
                        {
                            "role": "user",
                            "content": (
                                "HOST TARGET-RESOLUTION REQUIREMENT: Do not conclude "
                                "that the named device is absent yet. Call "
                                "homebrain_resolve_device with the user's device "
                                "wording; it performs bounded punctuation-tolerant "
                                "label searches without loading the full inventory."
                            ),
                        },
                    ])
                    continue
                if re.search(
                    r"\b(?:please confirm|ready to queue|have queued)\b",
                    answer,
                    re.I,
                ):
                    ungrounded_confirmation_claim_seen = True
                    messages.extend([
                        assistant,
                        {
                            "role": "user",
                            "content": (
                                "HOST CONFIRMATION ERROR: No structured sensitive "
                                "tool call was submitted, so no action is queued and "
                                "you must not ask for confirmation or claim it was "
                                "queued. Submit the complete tool call group now."
                            ),
                        },
                    ])
                    continue
                capability_decision = capability_grounding.decide(answer)
                if capability_decision.action is CapabilityAction.DISCOVER:
                    if capability_discovery:
                        capability_grounding.record_discovery(
                            len(capability_additions)
                        )
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": (
                                    f"{capability_decision.message}\n\n"
                                    "HOST DISCOVERY RESULT\n"
                                    f"{capability_discovery}"
                                ),
                            },
                        ])
                        continue
                    search_tool = catalog.declared_tool(SEARCH_TOOL)
                    if search_tool is not None:
                        execution = await self.executor.execute(
                            SEARCH_TOOL,
                            {"query": str(user_prompt).strip()},
                            tool=search_tool,
                            supports_live_claim=False,
                        )
                        additions = (
                            catalog.expand(execution.result)
                            if execution.result is not None
                            else []
                        )
                        capability_grounding.record_discovery(len(additions))
                        if additions:
                            tools = catalog.schemas()
                            logger.info(
                                "Capability recovery expanded registry with: %s",
                                ", ".join(item.name for item in additions),
                            )
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": (
                                    f"{capability_decision.message}\n\n"
                                    "HOST DISCOVERY RESULT\n"
                                    f"{execution.content}"
                                ),
                            },
                        ])
                        continue
                if (
                    capability_decision.action
                    is CapabilityAction.REJECT_UNGROUNDED
                ):
                    return str(capability_decision.message)
                decision = grounding.decide_no_tool_calls(
                    has_live_evidence=self.evidence.has_live_evidence()
                )
                if decision.action is GroundingAction.RETRY:
                    messages.extend([
                        assistant,
                        {"role": "user", "content": str(decision.message)},
                    ])
                    continue
                if decision.action is GroundingAction.REFUSE:
                    return str(decision.message)
                return str(assistant.get("content") or "Done.")
            sensitive: list[tuple[str, dict[str, Any]]] = []
            proposal_errors: list[tuple[str, str]] = []
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                arguments = dict(arguments)
                tool = catalog.declared_tool(name)
                effect = classify_tool_effect(tool, arguments)
                proposal_error = rule_machine_proposal_error(name, arguments)
                if proposal_error is not None and effect.mutates:
                    proposal_errors.append((name, proposal_error))
                if effect.mutates:
                    self._mutation_call_seen.set(True)
                if (
                    tool
                    and self.confirmation_policy.requires_confirmation(effect)
                ):
                    sensitive.append((name, arguments))
            if proposal_errors:
                messages.append(assistant)
                errors_by_name = dict(proposal_errors)
                for call in calls:
                    function = call.get("function") or {}
                    name = str(function.get("name") or "")
                    content = errors_by_name.get(
                        name,
                        (
                            "This action group was not executed because another "
                            "Rule Machine proposal in the group was invalid. "
                            "Resubmit the complete group after correcting it."
                        ),
                    )
                    messages.append({
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps({"error": content}),
                    })
                continue
            if sensitive:
                decision = self.confirmation_policy.decide(session_id, sensitive)
                if decision.action is ConfirmationAction.REJECT:
                    return str(decision.message)
                self.confirmations.queue(
                    session_id,
                    sensitive,
                    messages,
                    assistant,
                )
                return str(decision.message)
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
                tool = catalog.declared_tool(name)
                if not tool:
                    content = json.dumps({"error": f"Undeclared MCP tool: {name}"})
                else:
                    execution = await self.executor.execute(
                        name,
                        dict(arguments),
                        tool=tool,
                        supports_live_claim=name != "hub_search_tools",
                        evidence_kind=_EVIDENCE_KINDS.get(name, "tool_result"),
                    )
                    if execution.effect.mutates:
                        self._mutation_call_seen.set(True)
                    content = execution.content
                    result = execution.result
                    grounding.record_tool_outcome(
                        name,
                        dict(arguments),
                        success=execution.success,
                    )
                    if result is not None:
                        if name == "hub_search_tools":
                            additions = catalog.expand(result)
                            if additions:
                                tools = catalog.schemas()
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
                                name not in {_LOCAL_FILTER_TOOL, _LOCAL_QUERY_TOOL, _LOCAL_HOME_SNAPSHOT_TOOL, _LOCAL_WEATHER_TOOL}
                                or direct_home_snapshot
                            )
                            or not self._tool_succeeded(result)
                        ):
                            return deterministic_message
                messages.append({"role": "tool", "tool_name": name, "content": content})
                if name == _LOCAL_FILTER_TOOL and not post_filter_discovery_used:
                    search_tool = catalog.declared_tool(SEARCH_TOOL)
                    if search_tool is not None:
                        post_filter_discovery_used = True
                        messages.append({
                            "role": "user",
                            "content": (
                                "HOST POST-FILTER DISCOVERY RESULT\n"
                                f"{capability_discovery}\n"
                                "The local filter was an intermediate read, not proof that "
                                "the original request is complete. Use any newly declared "
                                "gateway needed to finish the original task."
                            ),
                        })
        logger.warning("Agent reached tool-round limit after %.3fs", time.monotonic() - request_started)
        if ungrounded_confirmation_claim_seen:
            return (
                "No Hubitat action was queued or executed because the model did not "
                "submit a complete structured action group. Please retry the original "
                "request."
            )
        return await self._final_answer(messages)


__all__ = ["AgentOutcome", "UnifiedMCPAgent"]
