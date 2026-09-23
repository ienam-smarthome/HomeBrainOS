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
from confirmed_action_coordinator import ConfirmedActionCoordinator
from confirmation_policy import ConfirmationAction, ConfirmationPolicy
from confirmation_store import CONFIRM_WORDS, ConfirmationStore, PendingConfirmation
from capability_grounding import CapabilityAction, CapabilityGroundingPolicy
from causal_evidence_planner import (
    controller_boundary_alignments,
    controller_history_arguments,
    render_controller_alignment_instruction,
    render_sensor_correlation_instruction,
    sensor_transition_correlations,
    subject_has_observed_intervals,
    subject_room_filter_arguments,
    trigger_sensor_history_arguments,
)
from causal_command_provenance import (
    command_producer_turn_on_sufficient,
    correlate_command_producers,
    render_command_producer_answer,
    render_command_producer_evidence,
)
from causal_subject_prefetch import causal_subject_seed
from causal_native_logs import (
    causal_boundary_log_windows,
    correlate_native_log_boundaries,
    native_log_causal_provenance_sufficient,
    native_log_open_start_sufficient,
    native_log_provenance_sufficient,
    render_native_log_correlation,
    render_strong_native_provenance_answer,
)
from causal_timeline import (
    causal_log_windows,
    render_command_source_followup,
    unresolved_material_timeline_rows,
)
from deterministic_tool_presenter import present_tool_result
from device_claim_grounding import (
    DeviceClaimAction,
    DeviceClaimGroundingPolicy,
    extract_receipt_device_ids,
    extract_tool_message_device_identities,
    find_named_device_mismatch,
)
from device_control_service import DeviceControlService
from device_history_service import DeviceHistoryService
from device_query_service import DeviceQueryService
from evidence_recorder import EvidenceRecorder
from final_answer_coordinator import FinalAnswerCoordinator
from grounding_policy import GroundingAction, GroundingPolicy
from hub_info_service import HubInfoService
from history_result_enrichment import inferred_state_retry_arguments
from investigation_policy import (
    is_causal_investigation,
    is_history_investigation,
    uses_known_history_evidence_path,
)
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from model_context_policy import ModelContextPolicy
from request_classification import (
    matches as _matches,
    requests_mutation as _requests_mutation,
    routine_control_arguments as _routine_control_arguments,
)
from reasoning_policy import set_reasoning_profile
from request_metrics import increment_active_metric
from rule_authoring_service import RuleAuthoringService
from rule_proposal_confirmation import RuleProposalConfirmation
from tool_executor import ToolExecutor
from tool_discovery_catalog import SEARCH_TOOL, ToolDiscoveryCatalog
from tool_catalog_assembly import build_request_tool_catalog
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
    LOCAL_LOCATION_EVENTS_TOOL as _LOCAL_LOCATION_EVENTS_TOOL,
    LOCAL_QUERY_TOOL as _LOCAL_QUERY_TOOL,
    LOCAL_RESOLVE_TOOL as _LOCAL_RESOLVE_TOOL,
    LOCAL_WEATHER_TOOL as _LOCAL_WEATHER_TOOL,
    ToolEffect,
    classify_tool_effect,
    normalize_rule_machine_proposal,
    rule_machine_proposal_error,
)

logger = logging.getLogger("HomeBrainOS.Orchestrator")


def _gateway_leaf(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    leaf = str(arguments.get("tool") or "").strip()
    inner = arguments.get("args")
    return leaf, dict(inner) if isinstance(inner, dict) else {}


def _is_broad_device_inventory_call(
    tool_name: str,
    arguments: dict[str, Any],
) -> bool:
    if tool_name not in {"hub_read_devices", "hub_manage_devices"}:
        return False
    leaf, inner = _gateway_leaf(arguments)
    if leaf != "hub_list_devices":
        return False
    scoped_keys = {
        "filter",
        "labelFilter",
        "capabilityFilter",
        "roomFilter",
        "changedSince",
        "attributeNames",
        "onlyOn",
        "cursor",
    }
    return not any(
        key in inner and inner.get(key) not in (None, "", [], {})
        for key in scoped_keys
    )


def _normalize_causal_log_call(
    tool_name: str,
    arguments: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Force native log reads onto observed causal boundary timestamps.

    Native hub logs interpret timezone-free values as UTC. Model-authored
    conversions can therefore shift a Hubitat-local +01:00 boundary by an hour.
    The host owns this conversion because the actual device-history timestamp is
    already structured evidence.
    """

    leaf, inner = _gateway_leaf(arguments)
    direct = tool_name == "hub_get_logs"
    gateway = leaf == "hub_get_logs"
    if not (direct or gateway):
        return arguments

    windows = causal_log_windows(evidence)
    if not windows:
        return arguments

    prior_log_reads = sum(
        1
        for receipt in evidence
        if isinstance(receipt, dict)
        and receipt.get("success") is True
        and (
            str(receipt.get("tool") or "") == "hub_get_logs"
            or str(receipt.get("sub_tool") or "") == "hub_get_logs"
        )
    )
    window = windows[min(prior_log_reads, len(windows) - 1)]
    normalized = dict(arguments)
    if direct:
        normalized["since"] = window["since"]
        normalized["until"] = window["until"]
        normalized.setdefault("limit", 100)
        return normalized

    normalized_inner = dict(inner)
    normalized_inner["since"] = window["since"]
    normalized_inner["until"] = window["until"]
    normalized_inner.setdefault("limit", 100)
    normalized["args"] = normalized_inner
    return normalized


def _controller_followup_arguments(
    candidates: list[dict[str, Any]],
) -> dict[str, str] | None:
    """Compatibility adapter for the pre-0.12 controller-selection contract."""

    return controller_history_arguments({
        "eventSourceHints": {"controllerCandidates": candidates}
    })


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

_READ_QUERY_PREFIX = re.compile(
    r"^\s*(?:why|when|what|which|where|how|is|are|was|were|did|does|do|"
    r"has|have|had)\b",
    re.I,
)


def _explicit_mutation_request(prompt: str) -> bool:
    """Return user write intent without treating diagnostic wording as a write.

    requests_mutation() is deliberately broad for routing/control detection and
    therefore matches phrases such as "why did the light turn off?" merely
    because they contain a control verb. Request semantics need a narrower
    contract: ordinary interrogatives remain reads, while imperative and polite
    action forms continue to use the established mutation parser.
    """

    text = str(prompt or "").strip()
    if not text:
        return False
    if _READ_QUERY_PREFIX.search(text):
        return False
    return _requests_mutation(text)

# Successful temporal history is strong structured evidence. Straight factual
# history requests can move directly to synthesis once the complete native tool
# round has executed. Investigative requests remain eligible for broader evidence
# gathering; classification lives in investigation_policy.py so the final
# coordinator and orchestrator cannot diverge.

# Live-observed, safety-relevant gap: a write-classified turn ("enable it",
# right after "disable humidity controller app" -> confirm -> disabled)
# returned "Enabled the '01. Humidity Controller' app." with model_rounds=1,
# tool_calls=0, and evidence=[] -- the model narrated a mutation success with
# no tool ever having executed. This only reaches the plain "return the
# model's own narration" branch at the bottom of the no-tool-calls handling
# below, which every other outcome (a queued confirmation, a rejected
# confirmation, a capability/device-claim/grounding refusal, a proposal
# error) already bypasses via its own earlier `return`. So checking right
# at that one fall-through point -- rather than message-sniffing for
# "already admits failure" wording, which turned out to be an unbounded
# and fragile set of legitimate phrasings elsewhere in this file -- reaches
# exactly the one case that was never verified: a mutation the model
# claimed but never actually attempted through a tool call this turn.
UNVERIFIED_MUTATION_REFUSAL = (
    "I could not verify that this action actually ran on Hubitat -- no "
    "successful tool result confirms it, so I will not report it as done."
)
RULE_WRITES_DISABLED_MESSAGE = (
    "Rule Machine writes are disabled in HomeBrain settings. "
    "No rule was queued or changed."
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
        model_name: str = "gemma4:31b-cloud",
        *,
        base_url: str = "https://ollama.com",
        timeout_seconds: float = 60,
        stream_idle_timeout_seconds: float = 20,
        local_base_url: str = "",
        local_model_name: str = "",
        local_timeout_seconds: float = 12,
        local_connect_timeout_seconds: float = 3,
        local_keep_alive_seconds: float = 120,
        tool_limit: int = 48,
        max_tool_rounds: int = 9,
        require_sensitive_confirmation: bool = True,
        confirmation_ttl_seconds: float = 120,
        rule_write_enabled: bool = True,
        causal_subject_prefetch_enabled: bool = True,
        causal_deterministic_final_enabled: bool = True,
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
            local_base_url=local_base_url,
            local_model_name=local_model_name,
            local_timeout_seconds=local_timeout_seconds,
            local_connect_timeout_seconds=local_connect_timeout_seconds,
            local_keep_alive_seconds=local_keep_alive_seconds,
        )
        self.tool_limit = max(1, int(tool_limit))
        self.max_tool_rounds = max(1, int(max_tool_rounds))
        self.require_sensitive_confirmation = bool(require_sensitive_confirmation)
        self.rule_write_enabled = bool(rule_write_enabled)
        self.causal_subject_prefetch_enabled = bool(
            causal_subject_prefetch_enabled
        )
        self.causal_deterministic_final_enabled = bool(
            causal_deterministic_final_enabled
        )
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
                _LOCAL_LOCATION_EVENTS_TOOL: self.device_history.location_events,
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
        self.final_answers = FinalAnswerCoordinator(
            self._chat,
            evidence_supplier=self.evidence.receipts,
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
        self._mutation_requested_by_user: ContextVar[bool] = ContextVar(
            "hubitat_mutation_requested_by_user", default=False
        )
        self.confirmed_actions = ConfirmedActionCoordinator(
            self.confirmation_policy,
            self.executor,
            self._chat,
            self._mark_mutation,
            rule_create_preflight=self.rule_authoring.duplicate_create_group_error,
        )
        self._rule_proposal_confirmation = RuleProposalConfirmation(
            self.confirmation_policy,
            self.confirmations,
            self._mutation_call_seen,
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

    def _invalidate_app_manifest(self) -> None:
        """Drop cached app/rule identities whenever the hub may have changed."""

        self._app_manifest = []
        self._app_manifest_at = 0.0

    def _mark_mutation(self) -> None:
        self._mutation_call_seen.set(True)
        self._invalidate_app_manifest()

    @property
    def api_key(self) -> str:
        return self.transport.api_key

    @property
    def model_name(self) -> str:
        return self.transport.model_name

    @property
    def local_configured(self) -> bool:
        return self.transport.local_configured

    @property
    def local_model_name(self) -> str:
        return self.transport.local_model_name

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
    async def _prefetch_explicit_causal_subject(
        self,
        user_prompt: str,
        *,
        catalog: ToolDiscoveryCatalog,
        completed_calls: set[str],
        messages: list[dict[str, Any]],
    ) -> tuple[str, str | None]:
        """Gather explicit switch-causal evidence before the first model round.

        This is deliberately narrower than general causal reasoning. It activates
        only when authoritative identity plus the prompt establish exactly one
        known switch device and an explicit on/off transition. The host then runs
        the same DeviceHistoryService and native-log correlation used by the
        ordinary model-selected path.

        Returns (status, canonical_subject_key), where status is one of:
        not_applicable, empty, sufficient, partial. The subject key lets the
        caller keep the prefetched device anchored as the investigative subject
        if later fallback reasoning inspects controller histories.
        """

        if not self.causal_subject_prefetch_enabled:
            return "not_applicable", None

        history_tool = catalog.declared_tool(_LOCAL_DEVICE_HISTORY_TOOL)
        if history_tool is None:
            return "not_applicable", None

        try:
            identities = await self.mcp.get_device_identities()
        except Exception as exc:
            logger.debug("Causal subject prefetch identity unavailable: %s", exc)
            return "not_applicable", None

        seed = causal_subject_seed(user_prompt, identities)
        if seed is None:
            return "not_applicable", None
        subject_key = re.sub(
            r"[^a-z0-9]", "", seed.name.casefold()
        ) or None

        arguments = {
            "name": seed.name,
            "attribute": seed.attribute,
            "_resolved_target": dict(seed.target),
            "_include_command_provenance": True,
            # DeviceHistoryService interprets an explicit small state-history
            # limit as "latest transitions over the bounded seven-day horizon"
            # while still fetching enough rows internally for interval analysis.
            "limit": 3,
        }
        signature = json.dumps(
            [_LOCAL_DEVICE_HISTORY_TOOL, arguments],
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        if signature in completed_calls:
            return "partial", subject_key
        completed_calls.add(signature)

        increment_active_metric("causal_subject_prefetch")
        execution = await self.executor.execute(
            _LOCAL_DEVICE_HISTORY_TOOL,
            arguments,
            tool=history_tool,
            supports_live_claim=True,
            evidence_kind=_EVIDENCE_KINDS[_LOCAL_DEVICE_HISTORY_TOOL],
        )
        messages.append({
            "role": "tool",
            "tool_name": _LOCAL_DEVICE_HISTORY_TOOL,
            "content": execution.content,
        })
        messages.append({
            "role": "user",
            "content": (
                "HOST CAUSAL SUBJECT PREFETCH\n"
                f"Authoritative identity matched the explicit transition subject to "
                f"{seed.name!r} (confidence={seed.confidence:.3f}); the host gathered "
                f"{seed.attribute} history before provider tool selection. Treat this "
                "as current-turn evidence and do not request the same subject history "
                "again merely to confirm it."
            ),
        })

        if not execution.success or execution.result is None:
            return "partial", subject_key
        data = (
            execution.result.data
            if isinstance(execution.result.data, dict)
            else {}
        )
        if not subject_has_observed_intervals(data):
            increment_active_metric("causal_subject_empty_stop")
            messages.append({
                "role": "user",
                "content": (
                    "HOST CAUSAL SUBJECT EVIDENCE STOP\n"
                    "The deterministic subject prefetch did not establish a bounded "
                    "active interval. Finalize from current-turn evidence only; do not "
                    "construct a cause for an unobserved transition."
                ),
            })
            return "empty", subject_key

        command_correlations = correlate_command_producers(
            self.evidence.receipts()
        )
        if command_producer_turn_on_sufficient(command_correlations):
            increment_active_metric("causal_command_producer_provenance")
            instruction = render_command_producer_evidence(
                command_correlations
            )
            if instruction:
                messages.append({"role": "user", "content": instruction})
            return "sufficient", subject_key

        sufficient = await self._collect_causal_boundary_logs(
            catalog=catalog,
            completed_calls=completed_calls,
            messages=messages,
        )
        return (
            ("sufficient", subject_key)
            if sufficient
            else ("partial", subject_key)
        )


    async def _collect_causal_boundary_logs(
        self,
        *,
        catalog: ToolDiscoveryCatalog,
        completed_calls: set[str],
        messages: list[dict[str, Any]],
    ) -> bool:
        """Collect both subject boundaries from native logs before weaker evidence.

        Native logs are the closest available execution provenance. Query both
        start and end boundaries host-side so a repeated physical-controller
        pattern can be tested deterministically without spending a model round
        choosing log windows.
        """

        diagnostics_tool = catalog.declared_tool("hub_read_diagnostics")
        if diagnostics_tool is None:
            return False

        windows = causal_boundary_log_windows(
            self.evidence.receipts(),
            max_intervals=1,
        )
        if not windows:
            return False

        pending: list[tuple[dict[str, Any], str]] = []
        for window in windows:
            arguments = {
                "tool": "hub_get_logs",
                "args": {
                    "limit": 100,
                    "since": window["since"],
                    "until": window["until"],
                },
            }
            signature = json.dumps(
                ["hub_read_diagnostics", arguments],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            if signature in completed_calls:
                continue
            completed_calls.add(signature)
            pending.append((arguments, window["boundaryRole"]))

        if not pending:
            correlations = correlate_native_log_boundaries(
                self.evidence.receipts()
            )
            return native_log_causal_provenance_sufficient(correlations)

        increment_active_metric("causal_native_log_reads", len(pending))

        async def read_one(
            arguments: dict[str, Any],
        ):
            return await self.executor.execute(
                "hub_read_diagnostics",
                arguments,
                tool=diagnostics_tool,
                supports_live_claim=True,
                evidence_kind="authoritative_native_log_history",
            )

        executions = await asyncio.gather(
            *(read_one(arguments) for arguments, _role in pending)
        )
        for (arguments, role), execution in zip(pending, executions):
            messages.append({
                "role": "tool",
                "tool_name": "hub_read_diagnostics",
                "content": execution.content,
            })
            messages.append({
                "role": "user",
                "content": (
                    "HOST NATIVE-LOG BOUNDARY READ\n"
                    f"Completed the host-derived {role} boundary log window "
                    f"{arguments['args']['since']} .. {arguments['args']['until']}. "
                    "This is direct current-turn provenance evidence."
                ),
            })

        correlations = correlate_native_log_boundaries(
            self.evidence.receipts()
        )
        if correlations:
            increment_active_metric(
                "causal_native_log_correlations",
                len(correlations),
            )
            instruction = render_native_log_correlation(correlations)
            if instruction:
                messages.append({"role": "user", "content": instruction})

        closed_sufficient = native_log_provenance_sufficient(correlations)
        open_sufficient = native_log_open_start_sufficient(correlations)
        if closed_sufficient:
            increment_active_metric("causal_repeated_controller_pattern")
        if open_sufficient:
            increment_active_metric("causal_open_start_provenance")
        return bool(closed_sufficient or open_sufficient)

    async def _expand_causal_subject_evidence(
        self,
        subject_history: dict[str, Any],
        *,
        catalog: ToolDiscoveryCatalog,
        completed_calls: set[str],
        messages: list[dict[str, Any]],
    ) -> bool:
        """Gather the fixed non-provenance causal evidence layer host-side.

        Causal reasoning should not spend separate model rounds rediscovering the
        same evidence classes. Native logs are tested first at both observed
        subject boundaries because they are stronger execution provenance than
        room correlation or app configuration. If a repeated physical-controller
        -> subject-command pattern is established at both boundaries, weaker
        discovery is skipped. Otherwise the established room/controller/location
        layer remains the compatibility fallback before one bounded provenance
        round.
        """

        expanded = False
        native_log_sufficient = await self._collect_causal_boundary_logs(
            catalog=catalog,
            completed_calls=completed_calls,
            messages=messages,
        )
        if native_log_sufficient:
            correlations = correlate_native_log_boundaries(
                self.evidence.receipts()
            )
            open_sufficient = native_log_open_start_sufficient(correlations)
            closed_sufficient = native_log_provenance_sufficient(correlations)
            detail = (
                "The subject interval is still OPEN. Native logs established a "
                "physical controller/input immediately before the subject ON "
                "command, with no closing OFF transition observed yet. This direct "
                "start-boundary execution timing is sufficient for the turn-on "
                "question; do not invent end-boundary corroboration or a duration."
                if open_sufficient and not closed_sufficient
                else (
                    "Repeated native-log provenance established the same physical "
                    "controller/input immediately before both the subject ON command "
                    "and the later OFF command."
                )
            )
            messages.append({
                "role": "user",
                "content": (
                    "HOST CAUSAL EVIDENCE LAYER COMPLETE\n"
                    + detail
                    + " This direct execution-timing evidence outranks room "
                    "correlation and app configuration, so do not fan out to weaker "
                    "device/sensor/location/config discovery. Final synthesis must "
                    "present the controller/input as the strongest initiating-control "
                    "candidate, distinguish downstream app reactions that occur after "
                    "the command, and retain the caveat that timing alone does not "
                    "independently prove the configured mapping or identify a person."
                ),
            })
            return True
        controller_checked = False
        room_arguments = subject_room_filter_arguments(subject_history)
        filter_tool = catalog.declared_tool(_LOCAL_FILTER_TOOL)

        if room_arguments is not None and filter_tool is not None:
            increment_active_metric("causal_room_plan")
            filter_execution = await self.executor.execute(
                _LOCAL_FILTER_TOOL,
                room_arguments,
                tool=filter_tool,
                supports_live_claim=True,
                evidence_kind=_EVIDENCE_KINDS[_LOCAL_FILTER_TOOL],
            )
            messages.append({
                "role": "tool",
                "tool_name": _LOCAL_FILTER_TOOL,
                "content": filter_execution.content,
            })
            completed_calls.add(json.dumps(
                [_LOCAL_FILTER_TOOL, room_arguments],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ))
            expanded = True
            filter_data = (
                filter_execution.result.data
                if filter_execution.result is not None
                and isinstance(filter_execution.result.data, dict)
                else {}
            )

            controller_arguments = controller_history_arguments(filter_data)
            controller_tool = catalog.declared_tool(_LOCAL_DEVICE_HISTORY_TOOL)
            if controller_arguments is not None and controller_tool is not None:
                controller_checked = True
                increment_active_metric("causal_provenance_read")
                controller_execution = await self.executor.execute(
                    _LOCAL_DEVICE_HISTORY_TOOL,
                    controller_arguments,
                    tool=controller_tool,
                    supports_live_claim=True,
                    evidence_kind=_EVIDENCE_KINDS[_LOCAL_DEVICE_HISTORY_TOOL],
                )
                messages.append({
                    "role": "tool",
                    "tool_name": _LOCAL_DEVICE_HISTORY_TOOL,
                    "content": controller_execution.content,
                })
                completed_calls.add(json.dumps(
                    [_LOCAL_DEVICE_HISTORY_TOOL, controller_arguments],
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ))

                controller_data = (
                    controller_execution.result.data
                    if controller_execution.result is not None
                    and isinstance(controller_execution.result.data, dict)
                    else {}
                )
                alignments = controller_boundary_alignments(
                    subject_history, controller_data
                )
                alignment_instruction = render_controller_alignment_instruction(
                    alignments
                )
                if alignment_instruction:
                    increment_active_metric(
                        "causal_provenance_aligned", len(alignments)
                    )
                    messages.append({
                        "role": "user",
                        "content": alignment_instruction,
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST CONTROLLER CORRELATION RESULT\n"
                            "The highest-ranked same-room controller was checked, "
                            "but no controller event aligned within two seconds of "
                            "any observed subject interval boundary. Treat that as "
                            "a negative correlation result, not proof that the "
                            "controller was uninvolved in every transition."
                        ),
                    })
            else:
                messages.append({
                    "role": "user",
                    "content": (
                        "HOST CONTROLLER CORRELATION RESULT\n"
                        "Exact-room discovery found no ranked button/controller "
                        "history candidate. Do not repeat the room scan."
                    ),
                })

            # One motion/presence history is justified only when material START
            # transitions remain unresolved after direct controller evidence.
            # This is capability-grounded from the same room scan and deliberately
            # excludes lux/temperature-only sensors.
            unresolved_after_controller = unresolved_material_timeline_rows(
                self.evidence.receipts()
            )
            sensor_arguments = (
                trigger_sensor_history_arguments(filter_data)
                if unresolved_after_controller
                else None
            )
            if sensor_arguments is not None and controller_tool is not None:
                increment_active_metric("causal_sensor_read")
                sensor_execution = await self.executor.execute(
                    _LOCAL_DEVICE_HISTORY_TOOL,
                    sensor_arguments,
                    tool=controller_tool,
                    supports_live_claim=True,
                    evidence_kind=_EVIDENCE_KINDS[_LOCAL_DEVICE_HISTORY_TOOL],
                )
                messages.append({
                    "role": "tool",
                    "tool_name": _LOCAL_DEVICE_HISTORY_TOOL,
                    "content": sensor_execution.content,
                })
                completed_calls.add(json.dumps(
                    [_LOCAL_DEVICE_HISTORY_TOOL, sensor_arguments],
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ))
                sensor_data = (
                    sensor_execution.result.data
                    if sensor_execution.result is not None
                    and isinstance(sensor_execution.result.data, dict)
                    else {}
                )
                correlations = sensor_transition_correlations(
                    subject_history,
                    sensor_data,
                )
                correlation_instruction = render_sensor_correlation_instruction(
                    correlations
                )
                if correlation_instruction:
                    increment_active_metric(
                        "causal_sensor_aligned",
                        len(correlations),
                    )
                    messages.append({
                        "role": "user",
                        "content": correlation_instruction,
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST MOTION/PRESENCE CORRELATION RESULT\n"
                            "The highest-ranked same-room MotionSensor/PresenceSensor "
                            "was checked, but no material subject boundary correlation "
                            "met the deterministic timing windows. Do not fan out to "
                            "additional environmental sensors."
                        ),
                    })

        # Location/mode correlation is a stable evidence class for causal
        # investigations and does not require model-authored tool selection.
        location_tool = catalog.declared_tool(_LOCAL_LOCATION_EVENTS_TOOL)
        if location_tool is not None:
            try:
                history_hours = int(subject_history.get("hoursBack") or 24)
            except (TypeError, ValueError):
                history_hours = 24
            location_arguments = {
                "hours_back": min(168, max(1, history_hours)),
                "limit": 50,
            }
            increment_active_metric("causal_location_read")
            location_execution = await self.executor.execute(
                _LOCAL_LOCATION_EVENTS_TOOL,
                location_arguments,
                tool=location_tool,
                supports_live_claim=True,
                evidence_kind=_EVIDENCE_KINDS[_LOCAL_LOCATION_EVENTS_TOOL],
            )
            messages.append({
                "role": "tool",
                "tool_name": _LOCAL_LOCATION_EVENTS_TOOL,
                "content": location_execution.content,
            })
            completed_calls.add(json.dumps(
                [_LOCAL_LOCATION_EVENTS_TOOL, location_arguments],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            ))
            expanded = True

        # If material turn-on transitions remain unresolved, give the bounded
        # provenance round app/rule identity context up front. This is navigation
        # only, not causal proof, but it lets the model inspect a relevant app
        # configuration in the SAME provenance round as logs rather than spending
        # a later round listing apps first.
        unresolved_material = unresolved_material_timeline_rows(
            self.evidence.receipts()
        )
        log_windows = causal_log_windows(self.evidence.receipts())
        if log_windows:
            rows = [
                (
                    f"- {item.get('timelineId') or 'transition'}: subject "
                    f"{item.get('subjectStart')} -> native-log UTC window "
                    f"{item.get('since')} .. {item.get('until')}"
                )
                for item in log_windows
            ]
            messages.append({
                "role": "user",
                "content": (
                    "HOST CAUSAL NATIVE-LOG WINDOWS\n"
                    + "\n".join(rows)
                    + "\nThese UTC boundaries were derived from the observed "
                    "Hubitat event timestamps. When selecting hub_get_logs, do not "
                    "invent or manually convert a clock time; the host will enforce "
                    "the matching since/until window on the call."
                ),
            })
        if (
            unresolved_material
            and "hub_read_apps_code" in catalog.available_names
        ):
            apps = await self._cached_app_manifest()
            if apps:
                increment_active_metric("causal_app_navigation")
                messages.append({
                    "role": "user",
                    "content": (
                        "HOST CAUSAL APP/RULE NAVIGATION\n"
                        + render_app_manifest(apps)
                        + "\nThis installed-app manifest is navigation context, "
                        "not evidence that any app caused the subject transition. "
                        "During the single bounded provenance round, prefer a "
                        "relevant app/rule DETAIL read (for example app config or "
                        "rule execution/config) alongside logs when both materially "
                        "test the unresolved transition. Do not spend the round "
                        "listing apps again."
                    ),
                })

        messages.append({
            "role": "user",
            "content": (
                "HOST CAUSAL EVIDENCE LAYER COMPLETE\n"
                "The host has completed the fixed subject-adjacent evidence "
                "layer: exact-room controller evidence when available; one "
                "capability-grounded motion/presence sensor when unresolved material "
                "turn-ons justified it; plus location/mode history clipped to the "
                "active history window. Do not request more device, sensor, "
                "controller, room, or "
                "location histories merely to be thorough. The next step is one "
                "bounded provenance selection from installed read-only log/rule/"
                "app gateways. When unresolved material transitions remain and "
                "app/rule identities were supplied above, issue up to two "
                "complementary reads in this SAME model round (for example logs "
                "plus one relevant app/rule detail), then synthesize."
            ),
        })
        return expanded

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
        """Never preload the full device inventory for a mutation.

        Every model-routed write must resolve its named target through the
        targeted local resolver.  Preloading all devices duplicates that work
        and live testing showed it adds roughly 30 seconds for 124 devices.
        App identity is handled separately by the bounded app manifest.
        """

        return False

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

    async def _system_prompt(
        self, user_prompt: str = "", conversation_history: Any = None
    ) -> str:
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
        previous_user_prompt = ""
        for message in reversed(self._history(conversation_history)):
            if message.get("role") != "user":
                continue
            content = str(message.get("content") or "")
            if content.strip().casefold() in CONFIRM_WORDS:
                continue
            previous_user_prompt = content
            break
        if (
            _matches(user_prompt, _APP_TERMS)
            or _matches(previous_user_prompt, _APP_TERMS)
        ):
            # App/rule identity context is loaded only when the conversation
            # actually asks for that evidence class. Generic investigations begin
            # from the fixed local history registry and activate the bounded
            # provenance registry later only when subject evidence warrants it.
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

    def _unverified_mutation_guard(self, content: str) -> str:
        mutation_expected = (
            self._mutation_requested_by_user.get()
            or self._mutation_call_seen.get()
        )
        if mutation_expected and not any(
            receipt.get("success") and receipt.get("mutates")
            for receipt in self.evidence.receipts()
        ):
            return UNVERIFIED_MUTATION_REFUSAL
        return content

    async def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        content = await self.final_answers.answer(messages)
        return self._unverified_mutation_guard(content)

    def _take_confirmation(self, session_id: str, prompt: str) -> PendingConfirmation | None:
        return self.confirmations.consume(session_id, prompt)

    @staticmethod
    def _rule_result_data(execution: Any) -> dict[str, Any]:
        return ConfirmedActionCoordinator.rule_result_data(execution)

    @classmethod
    def _verified_rule_execution(cls, execution: Any) -> bool:
        return ConfirmedActionCoordinator.verified_rule_execution(execution)

    @staticmethod
    def _queued_rule_name(arguments: dict[str, Any]) -> str:
        return ConfirmedActionCoordinator.queued_rule_name(arguments)

    def _confirmed_rule_report(
        self,
        outcomes: list[tuple[str, dict[str, Any], Any]],
        *,
        queued_count: int,
    ) -> str | None:
        return ConfirmedActionCoordinator.confirmed_rule_report(
            outcomes,
            queued_count=queued_count,
        )

    async def _resume_confirmation(self, pending: PendingConfirmation, catalog: ToolDiscoveryCatalog) -> str:
        return await self.confirmed_actions.resume(pending, catalog)

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
        mutation_request_token = self._mutation_requested_by_user.set(
            _explicit_mutation_request(user_prompt)
        )
        class_token = self._request_class.set("tool-driven")
        try:
            message = await self._process_user_request(
                user_prompt,
                conversation_history,
                session_id=session_id,
            )
            evidence = self.evidence.receipts()
            if (
                self._mutation_requested_by_user.get()
                or self._mutation_call_seen.get()
            ):
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
            self._mutation_requested_by_user.reset(mutation_request_token)
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
        catalog = build_request_tool_catalog(all_tools)
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
        known_history_path = uses_known_history_evidence_path(user_prompt)
        if known_history_path:
            increment_active_metric("history_known_tool_fastpath")
        if (
            not self.rule_write_enabled
            and self.rule_authoring.matches_request(user_prompt)
        ):
            return RULE_WRITES_DISABLED_MESSAGE
        if (
            search_tool is not None
            and not self._is_conversational_prompt(user_prompt)
            and not known_history_path
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
            available_gateways=set(catalog.available_names),
            can_read_rules=True,
        )
        if rule_decision.handled:
            return self._rule_proposal_confirmation.resolve(
                rule_decision,
                user_prompt=user_prompt,
                session_id=session_id,
            )
        tools = catalog.schemas()
        prompt_started = time.monotonic()
        system_prompt = await self._system_prompt(user_prompt, conversation_history)
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
        device_claim_grounding = DeviceClaimGroundingPolicy()
        post_filter_discovery_used = False
        causal_request = is_causal_investigation(user_prompt)
        investigative_request = is_history_investigation(user_prompt)
        set_reasoning_profile(
            "investigative" if investigative_request else "standard"
        )
        investigative_subject_history_key: str | None = None
        causal_subject_evidence_expanded = False
        causal_subject_no_intervals = False
        ungrounded_confirmation_claim_seen = False
        last_proposal_error: tuple[str, dict[str, Any], str] | None = None
        proposal_error_retries = 0
        causal_completion_retry_used = False
        causal_completion_mode = False

        if causal_request:
            causal_prefetch, prefetched_subject_key = (
                await self._prefetch_explicit_causal_subject(
                    user_prompt,
                    catalog=catalog,
                    completed_calls=completed_calls,
                    messages=messages,
                )
            )
            if prefetched_subject_key:
                investigative_subject_history_key = prefetched_subject_key
            if causal_prefetch == "sufficient":
                deterministic_answer = (
                    (
                        render_command_producer_answer(
                            self.evidence.receipts()
                        )
                        or render_strong_native_provenance_answer(
                            self.evidence.receipts()
                        )
                    )
                    if self.causal_deterministic_final_enabled
                    else None
                )
                if deterministic_answer:
                    increment_active_metric(
                        "causal_deterministic_finalization"
                    )
                    increment_active_metric("investigative_finalization")
                    return deterministic_answer
                increment_active_metric("investigative_finalization")
                return await self._final_answer(messages)
            if causal_prefetch == "empty":
                increment_active_metric("investigative_finalization")
                return await self._final_answer(messages)

        for _ in range(self.max_tool_rounds):
            if causal_completion_mode:
                catalog.activate_causal_provenance_view()
                tools = catalog.schemas()
            assistant = await self._chat(messages, tools)
            calls = assistant.get("tool_calls") or []
            if not calls:
                if last_proposal_error is not None:
                    name, rejected_arguments, reason = last_proposal_error
                    increment_active_metric("proposal_validation_failures")
                    rejected = json.dumps(
                        {"tool": name, "arguments": rejected_arguments},
                        sort_keys=True,
                        ensure_ascii=False,
                        default=str,
                    )
                    return (
                        "No Hubitat action was queued or executed because Rule "
                        f"Machine proposal validation failed. Exact reason: {reason} "
                        f"Rejected payload: {rejected}"
                    )
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
                receipt_device_ids = extract_receipt_device_ids(
                    self.evidence.receipts()
                )
                if receipt_device_ids:
                    # Device-claim grounding is an auxiliary final-answer guard;
                    # it must not trigger a new complete-inventory read after the
                    # model has already synthesized its answer. Reuse any detailed
                    # manifest already cached for another reason and supplement it
                    # with id/label pairs from this turn's structured tool results.
                    # The latter covers common targeted reads such as
                    # homebrain_device_history even when the full cache is empty.
                    peek_cached = getattr(self.mcp, "peek_cached_devices", None)
                    known_devices = (
                        list(peek_cached()) if callable(peek_cached) else []
                    )
                    known_devices.extend(
                        extract_tool_message_device_identities(messages)
                    )
                    mismatched_label = find_named_device_mismatch(
                        answer,
                        known_devices,
                        receipt_device_ids,
                    )
                    device_claim_decision = device_claim_grounding.decide(
                        mismatched_label
                    )
                    if device_claim_decision.action is DeviceClaimAction.RETRY:
                        messages.extend([
                            assistant,
                            {
                                "role": "user",
                                "content": str(device_claim_decision.message),
                            },
                        ])
                        continue
                    if device_claim_decision.action is DeviceClaimAction.REFUSE:
                        return str(device_claim_decision.message)
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

                # A causal investigation with observed boundary commands still has
                # one unresolved provenance slot until an app/rule/log source is
                # checked. Give the tool loop one bounded chance to fill that slot.
                # If the model declines or no stronger source exists, final
                # synthesis will explicitly preserve the gap instead of guessing.
                if causal_request and not causal_completion_retry_used:
                    followup = render_command_source_followup(
                        self.evidence.receipts()
                    )
                    if followup:
                        causal_completion_retry_used = True
                        causal_completion_mode = True
                        increment_active_metric("causal_completion_retry")
                        messages.extend([
                            assistant,
                            {"role": "user", "content": followup},
                        ])
                        continue

                # All investigative completions go through the shared final
                # coordinator. Previously a voluntary no-tool model response
                # bypassed the evidence brief, causal timeline, and validators,
                # so production could gather strong evidence and still omit it.
                if investigative_request:
                    increment_active_metric("investigative_finalization")
                    return await self._final_answer(messages)

                return self._unverified_mutation_guard(
                    str(assistant.get("content") or "Done.")
                )
            if causal_completion_mode:
                allowed_completion_tools = set(catalog.causal_provenance_names())
                disallowed_completion_calls = [
                    call
                    for call in calls
                    if str((call.get("function") or {}).get("name") or "")
                    not in allowed_completion_tools
                ]
                if disallowed_completion_calls:
                    messages.append(assistant)
                    for call in calls:
                        function = call.get("function") or {}
                        name = str(function.get("name") or "")
                        messages.append({
                            "role": "tool",
                            "tool_name": name,
                            "content": json.dumps({
                                "error": (
                                    "Causal completion is restricted to read-only "
                                    "app/rule/log provenance tools. Device, sensor, "
                                    "location, and mutation tools are not available "
                                    "in this bounded phase."
                                ),
                            }),
                        })
                    increment_active_metric("investigative_finalization")
                    return await self._final_answer(messages)

            sensitive: list[tuple[str, dict[str, Any]]] = []
            round_actions: list[tuple[str, dict[str, Any]]] = []
            proposal_errors: list[tuple[str, str]] = []
            round_has_mutation = False
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                arguments = dict(arguments)
                arguments = normalize_rule_machine_proposal(name, arguments)
                round_actions.append((name, arguments))
                tool = catalog.declared_tool(name)
                effect = classify_tool_effect(tool, arguments)
                if (
                    not self.rule_write_enabled
                    and name == ConfirmedActionCoordinator.RULE_GATEWAY
                    and effect.mutates
                ):
                    return RULE_WRITES_DISABLED_MESSAGE
                proposal_error = rule_machine_proposal_error(
                    name, arguments, user_prompt=user_prompt
                )
                if proposal_error is not None and effect.mutates:
                    proposal_errors.append((name, proposal_error))
                if tool is not None and effect.mutates:
                    round_has_mutation = True
                    self._mark_mutation()
                if (
                    tool
                    and self.confirmation_policy.requires_confirmation(effect)
                ):
                    sensitive.append((name, arguments))
            if proposal_errors:
                failed_name, failed_reason = proposal_errors[0]
                failed_arguments = next(
                    (
                        arguments
                        for name, arguments in round_actions
                        if name == failed_name
                    ),
                    {},
                )
                last_proposal_error = (
                    failed_name,
                    failed_arguments,
                    failed_reason,
                )
                proposal_error_retries += 1
                if proposal_error_retries >= 2:
                    increment_active_metric("proposal_validation_failures")
                    rejected = json.dumps(
                        {"tool": failed_name, "arguments": failed_arguments},
                        sort_keys=True,
                        ensure_ascii=False,
                        default=str,
                    )
                    return (
                        "No Hubitat action was queued or executed because Rule "
                        "Machine proposal validation failed twice. Exact reason: "
                        f"{failed_reason} Rejected payload: {rejected}"
                    )
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
            rule_create_error = (
                await self.rule_authoring.duplicate_create_group_error([
                    arguments
                    for name, arguments in round_actions
                    if name == ConfirmedActionCoordinator.RULE_GATEWAY
                ])
            )
            if rule_create_error is not None:
                return rule_create_error
            if sensitive:
                last_proposal_error = None
                decision = self.confirmation_policy.decide(session_id, sensitive)
                if decision.action is ConfirmationAction.REJECT:
                    return str(decision.message)
                self.confirmations.queue(
                    session_id,
                    round_actions,
                    messages,
                    assistant,
                )
                return str(decision.message)
            messages.append(assistant)
            duplicate_signature_seen = False
            round_history_evidence_sufficient = False
            round_tool_failure = False
            causal_subject_to_expand: dict[str, Any] | None = None
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments or "{}")
                arguments = dict(arguments)
                if causal_request:
                    arguments = _normalize_causal_log_call(
                        name,
                        arguments,
                        self.evidence.receipts(),
                    )
                signature = json.dumps([name, arguments], sort_keys=True, ensure_ascii=False, default=str)
                if signature in completed_calls:
                    duplicate_signature_seen = True
                    messages.append({
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps({
                            "note": (
                                "Skipped: identical to a call already "
                                "executed earlier this turn."
                            ),
                        }),
                    })
                    continue
                completed_calls.add(signature)
                # Every call gets fresh history-reasoning flags.  Keeping
                # these per call avoids state leaking from a prior tool in a
                # mixed round or an undeclared-tool branch.
                history_reasoning_bypass = False
                investigative_history_bypass = False
                tool = catalog.declared_tool(name)
                requested_history_name = str(arguments.get("name") or "").strip()
                requested_history_key = re.sub(
                    r"[^a-z0-9]", "", requested_history_name.casefold()
                )
                redundant_causal_room_filter = bool(
                    causal_request
                    and causal_subject_evidence_expanded
                    and name == _LOCAL_FILTER_TOOL
                    and str(arguments.get("attribute") or "").strip().casefold() == "room"
                )
                broad_causal_inventory = bool(
                    causal_request
                    and _is_broad_device_inventory_call(name, arguments)
                )
                missing_related_attribute = bool(
                    investigative_request
                    and name == _LOCAL_DEVICE_HISTORY_TOOL
                    and investigative_subject_history_key
                    and requested_history_key
                    and requested_history_key != investigative_subject_history_key
                    and not str(arguments.get("attribute") or "").strip()
                )
                gateway_error = (
                    catalog.gateway_operation_error(name, arguments)
                    if tool is not None
                    else None
                )
                if not tool:
                    round_tool_failure = True
                    content = json.dumps({"error": f"Undeclared MCP tool: {name}"})
                elif redundant_causal_room_filter:
                    content = json.dumps({
                        "note": (
                            "Skipped: exact-room causal evidence discovery was already "
                            "completed host-side from the resolved subject metadata. "
                            "Use the gathered controller/provenance evidence and move "
                            "to a different evidence class."
                        )
                    })
                elif broad_causal_inventory:
                    round_tool_failure = True
                    increment_active_metric("causal_broad_inventory_blocked")
                    content = json.dumps({
                        "error": (
                            "Broad hub_list_devices inventory reads are not a causal "
                            "provenance source and are blocked for this investigation. "
                            "Use homebrain_device_history/homebrain_resolve_device for "
                            "the named subject, or a scoped labelFilter/roomFilter when "
                            "a genuinely new device identity is required."
                        )
                    })
                elif missing_related_attribute:
                    round_tool_failure = True
                    increment_active_metric("investigative_attribute_required")
                    content = json.dumps({
                        "error": (
                            "Investigative related-device history requires an explicit "
                            "attribute. Choose the material capability you intend to "
                            "compare (for example motion, illuminance, contact, switch) "
                            "and retry homebrain_device_history with attribute=... . "
                            "Do not infer absence of an attribute from generic history."
                        )
                    })
                elif gateway_error is not None:
                    round_tool_failure = True
                    increment_active_metric("gateway_operation_rejected")
                    content = json.dumps({
                        "error": (
                            f"Gateway/sub-tool compatibility check rejected this call: "
                            f"{gateway_error}"
                        )
                    })
                else:
                    execution = await self.executor.execute(
                        name,
                        dict(arguments),
                        tool=tool,
                        supports_live_claim=name != "hub_search_tools",
                        evidence_kind=_EVIDENCE_KINDS.get(name, "tool_result"),
                    )
                    if execution.effect.mutates:
                        self._mark_mutation()
                    grounding.record_tool_outcome(
                        name,
                        dict(arguments),
                        success=execution.success,
                    )

                    # A causal subject read may begin attribute-less, infer one
                    # binary state from a full mixed page, yet still establish
                    # no bounded interval because the older opposite boundary
                    # was crowded out by noisy telemetry. Before the host is
                    # allowed to declare an empty causal subject, deterministically
                    # retry that same canonical device once with the inferred
                    # state attribute. This is host-generated, so it consumes no
                    # additional model round or model-directed read budget.
                    if (
                        causal_request
                        and name == _LOCAL_DEVICE_HISTORY_TOOL
                        and execution.success
                        and execution.result is not None
                    ):
                        retry_arguments = inferred_state_retry_arguments(
                            name,
                            arguments,
                            execution.result,
                        )
                        if retry_arguments is not None:
                            retry_signature = json.dumps(
                                [name, retry_arguments],
                                sort_keys=True,
                                ensure_ascii=False,
                                default=str,
                            )
                            if retry_signature not in completed_calls:
                                completed_calls.add(retry_signature)
                                increment_active_metric(
                                    "causal_inferred_attribute_retry"
                                )
                                retry_execution = await self.executor.execute(
                                    name,
                                    retry_arguments,
                                    tool=tool,
                                    supports_live_claim=True,
                                    evidence_kind=_EVIDENCE_KINDS.get(
                                        name, "tool_result"
                                    ),
                                )
                                grounding.record_tool_outcome(
                                    name,
                                    dict(retry_arguments),
                                    success=retry_execution.success,
                                )
                                if (
                                    retry_execution.success
                                    and retry_execution.result is not None
                                ):
                                    execution = retry_execution

                    content = execution.content
                    result = execution.result
                    if not execution.success:
                        round_tool_failure = True
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
                        history_reasoning_bypass = (
                            name == _LOCAL_DEVICE_HISTORY_TOOL
                            and self._tool_succeeded(result)
                        )
                        temporal_history_answer_ready = (
                            history_reasoning_bypass
                            and isinstance(result.data, dict)
                            and isinstance(result.data.get("temporalAnalysis"), dict)
                        )
                        investigative_history_bypass = (
                            history_reasoning_bypass and investigative_request
                        )
                        first_investigative_subject = bool(
                            investigative_history_bypass
                            and investigative_subject_history_key is None
                        )
                        if first_investigative_subject:
                            resolved_subject = str(
                                result.data.get("label")
                                or result.data.get("requested")
                                or requested_history_name
                                or ""
                            ).strip()
                            investigative_subject_history_key = re.sub(
                                r"[^a-z0-9]", "", resolved_subject.casefold()
                            ) or None
                            if causal_request and isinstance(result.data, dict):
                                causal_subject_to_expand = dict(result.data)
                                if not subject_has_observed_intervals(result.data):
                                    causal_subject_no_intervals = True
                        if (
                            deterministic_message is not None
                            and not history_reasoning_bypass
                            and (
                                (
                                    name not in {_LOCAL_FILTER_TOOL, _LOCAL_QUERY_TOOL, _LOCAL_HOME_SNAPSHOT_TOOL, _LOCAL_WEATHER_TOOL}
                                    or direct_home_snapshot
                                )
                                or not self._tool_succeeded(result)
                            )
                        ):
                            return deterministic_message
                messages.append({"role": "tool", "tool_name": name, "content": content})
                if history_reasoning_bypass and not investigative_history_bypass:
                    if temporal_history_answer_ready:
                        round_history_evidence_sufficient = True
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST HISTORY-SYNTHESIS HINT\n"
                            "The successful device-history result is evidence, not the "
                            "finished answer. Answer the user's original question "
                            "directly from the current-turn history evidence. When "
                            "temporalAnalysis is present, use its pre-computed interval "
                            "and reliability fields instead of redoing timestamp "
                            "arithmetic yourself. Treat durationReliability="
                            "unverified-event-stream or sourceIntegrityVerified=false "
                            "as an estimate only: do not call it exact, continuous, or "
                            "a mathematical lower bound. Do not call unrelated context "
                            "tools merely to be thorough. State changes do not prove "
                            "which automation or person caused them."
                        ),
                    })
                elif history_reasoning_bypass and investigative_history_bypass:
                    messages.append({
                        "role": "user",
                        "content": (
                            "HOST INVESTIGATIVE-HISTORY REQUIREMENT\n"
                            "The user asked for analysis beyond a duration/event list. "
                            "Use the recorded rows to identify concrete patterns, but "
                            "keep observation separate from interpretation. Gather "
                            "additional evidence by quality, not by exhaustiveness: "
                            "(1) direct provenance/log evidence, when available; "
                            "(2) rule/app state or app event history tied to the subject; "
                            "(3) location/mode events close to the subject transition; "
                            "(4) same-room controller/button/remote event history when "
                            "the room discovery result exposes controller candidates; "
                            "(5) a small number of materially relevant environmental "
                            "sensor histories. For why/cause/trigger questions, prefer "
                            "controller events such as pushed, held, released, or "
                            "doubleTapped over motion/illuminance when both are available, "
                            "because an aligned control event is closer to direct provenance. "
                            "When checking any related device with multiple capabilities, "
                            "request the specific history attribute you intend to reason "
                            "about; generic device history is not evidence "
                            "that an omitted attribute had no events. Prefer a stronger "
                            "source over several weaker correlations and stop once the "
                            "available evidence "
                            "can support a bounded conclusion. If a needed gateway "
                            "sub-tool is not already established by the declared schema "
                            "or discovery result, use hub_search_tools for that exact "
                            "operation instead of guessing a gateway. For a why/cause/trigger "
                            "question, device history proves what changed but not the "
                            "cause; do not attribute a cause without direct or materially "
                            "corroborating current-turn evidence. For normal/abnormal/"
                            "expected/unusual wording, do not invent a generic notion "
                            "of normality: describe objective patterns that stand out, "
                            "and say a baseline or explicit expected rule is needed for "
                            "a stronger normality judgement. For comparison/correlation, "
                            "obtain the other requested side of the comparison. Avoid "
                            "room-wide or whole-hub evidence sweeps merely to be "
                            "thorough. Any unverified-event-stream duration remains an "
                            "estimate, not an exact total or proof of continuity."
                        ),
                    })
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
            if causal_subject_no_intervals:
                increment_active_metric("causal_subject_empty_stop")
                messages.append({
                    "role": "user",
                    "content": (
                        "HOST CAUSAL SUBJECT EVIDENCE STOP\n"
                        "The current-turn subject history did not establish any "
                        "bounded active interval in the requested window. Do not "
                        "expand to controller, sensor, location, app, rule, or log "
                        "evidence to reconstruct an older or hypothetical causal "
                        "timeline. Finalize from CURRENT-TURN evidence only. State "
                        "that no bounded subject interval was established and that "
                        "an unverified/incomplete event stream does not prove the "
                        "device stayed inactive."
                    ),
                })
                return await self._final_answer(messages)

            if (
                causal_subject_to_expand is not None
                and not causal_subject_evidence_expanded
            ):
                causal_subject_evidence_expanded = (
                    await self._expand_causal_subject_evidence(
                        causal_subject_to_expand,
                        catalog=catalog,
                        completed_calls=completed_calls,
                        messages=messages,
                    )
                )
                if native_log_causal_provenance_sufficient(
                    correlate_native_log_boundaries(
                        self.evidence.receipts()
                    )
                ):
                    increment_active_metric("investigative_finalization")
                    return await self._final_answer(messages)

                if not causal_completion_retry_used:
                    # Once the subject has real transitions, all stable
                    # subject-adjacent evidence is gathered host-side. Never
                    # reopen the unrestricted general tool loop: move directly
                    # into one constrained provenance-selection round.
                    followup = render_command_source_followup(
                        self.evidence.receipts()
                    ) or (
                        "HOST BOUNDED CAUSAL PROVENANCE PHASE\n"
                        "Observed subject transitions are established and the "
                        "fixed controller/location evidence layer is complete. "
                        "Choose only the materially strongest installed read-only "
                        "log/rule/app provenance source(s) from the tools now "
                        "declared. Do not search for device/sensor context and do "
                        "not request mutations. After this one tool round, the "
                        "host will synthesize from the complete current-turn "
                        "evidence."
                    )
                    causal_completion_retry_used = True
                    causal_completion_mode = True
                    increment_active_metric("causal_completion_retry")
                    messages.append({"role": "user", "content": followup})
                    continue

            if causal_completion_mode:
                # Installed provenance gateways are offered directly. As soon as
                # the bounded completion round attempts a provenance read,
                # synthesize from what it returned instead of opening another
                # exploratory round. Search remains only a sparse-registry
                # compatibility fallback.
                completion_read_attempted = any(
                    name != SEARCH_TOOL
                    for name, _arguments in round_actions
                )
                if completion_read_attempted:
                    increment_active_metric("investigative_finalization")
                    return await self._final_answer(messages)

            if duplicate_signature_seen:
                return await self._final_answer(messages)
            if (
                round_history_evidence_sufficient
                and not round_has_mutation
                and not round_tool_failure
            ):
                # The model already chose the complete native tool round for this
                # step. If that round produced a successful deterministic temporal
                # history and the request is not investigative, the history evidence is
                # sufficient for synthesis. Execute every call the model requested
                # in the round, then stop tool expansion instead of letting a later
                # round wander into location/motion/rule reads merely for context.
                increment_active_metric("evidence_sufficiency_stop")
                return await self._final_answer(messages)
        logger.warning("Agent reached tool-round limit after %.3fs", time.monotonic() - request_started)
        if ungrounded_confirmation_claim_seen:
            return (
                "No Hubitat action was queued or executed because the model did not "
                "submit a complete structured action group. Please retry the original "
                "request."
            )
        if last_proposal_error is not None:
            name, rejected_arguments, reason = last_proposal_error
            increment_active_metric("proposal_validation_failures")
            rejected = json.dumps(
                {"tool": name, "arguments": rejected_arguments},
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            return (
                "No Hubitat action was queued or executed because Rule Machine "
                f"proposal validation failed. Exact reason: {reason} Rejected "
                f"payload: {rejected}"
            )
        return await self._final_answer(messages)


__all__ = ["AgentOutcome", "UnifiedMCPAgent", "_controller_followup_arguments"]
