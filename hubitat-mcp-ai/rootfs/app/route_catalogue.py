from __future__ import annotations

import re

from active_rooms_route import is_active_rooms_query
from ai_evidence_planner import is_ai_evidence_query
from automation_recommendation import AutomationRecommendationService
from backup_intent import is_explicit_backup_request
from climate_metric_extrema_route import _metric_request
from control_agent_intent import is_control_candidate
from control_focus_octopus_energy import is_octopus_energy_query
from device_health_fast_route import is_attention_query, is_device_health_query
from fast_fallback_extended_reads import is_hub_logs_query
from home_priority_insight import is_home_priority_query
from mcp_agent_orchestrator import _is_explicit_device_lookup, _requested_device_attribute
from named_rule_control import parse_named_rule_intent
from named_rule_status_route import parse_rule_status_target
from power_accounting import is_power_accounting_query
from recent_log_diagnostics_route import is_recent_log_diagnostics_query
from route_registry import RouteDescriptor, RouteRegistry
from semantic_home_summary_agent import _HOME_SUMMARY_RE
from thermostat_summary_guard import _DIRECT_THERMOSTAT_QUERY


_ENERGY_QUERY = re.compile(
    r"\b(?:whole[- ]house\s+)?(?:power|energy|consumption|usage)\b",
    re.IGNORECASE,
)
_RESTART_OR_FIRMWARE = re.compile(
    r"\b(?:restart|reboot|firmware\s+update|update\s+(?:the\s+)?hub)\b",
    re.IGNORECASE,
)
_CONFIRMATION_REPLY = re.compile(
    r"^(?:yes|no|confirm|cancel|proceed|do it)[.!?]*$",
    re.IGNORECASE,
)


def _measurement_query(query: str) -> bool:
    return _requested_device_attribute(query) is not None or _is_explicit_device_lookup(query)


def _has_match(value: object) -> bool:
    return value is not None


def build_route_registry() -> RouteRegistry:
    """Return the safety-aware route catalogue used by passive diagnostics.

    Existing handlers remain authoritative. The metadata here describes their
    capability, required MCP evidence and runtime identifiers so overlap and
    agreement measurements compare like with like during incremental migration.
    """

    return RouteRegistry(
        (
            RouteDescriptor(
                name="pending-confirmation",
                priority=1000,
                terminal=True,
                matcher=lambda query: bool(_CONFIRMATION_REPLY.match(query.strip())),
                reason="confirmation replies must be consumed before generic routing",
                capability_id="confirmation.consume",
                safety_class="mutate",
                slot_schema=(("decision", "confirmation", True),),
            ),
            RouteDescriptor(
                name="hub-administration",
                priority=950,
                terminal=True,
                matcher=lambda query: bool(_RESTART_OR_FIRMWARE.search(query)),
                reason="destructive hub administration requires a dedicated confirmation workflow",
                capability_id="hub.administration",
                mcp_tools=("hub_create_backup", "hub_reboot", "hub_update_firmware"),
                safety_class="destructive",
                slot_schema=(("operation", "hub-administration-action", True),),
                runtime_intents=(
                    "hub-restart-confirmation-required",
                    "hub-restart",
                    "hub-firmware-update-confirmation-required",
                    "hub-firmware-update",
                ),
            ),
            RouteDescriptor(
                name="hub-backup",
                priority=940,
                terminal=True,
                matcher=is_explicit_backup_request,
                reason="explicit backup requests use the dedicated live backup workflow",
                capability_id="hub.backup",
                mcp_tools=("hub_create_backup",),
                safety_class="mutate",
                runtime_intents=("hub-backup",),
            ),
            RouteDescriptor(
                name="named-rule-control",
                priority=930,
                terminal=True,
                matcher=lambda query: _has_match(parse_named_rule_intent(query)),
                reason="named rule writes resolve an exact rule before mutation",
                capability_id="automation.rule-control",
                mcp_tools=(
                    "hub_list_rules",
                    "hub_set_rule_paused",
                    "hub_call_rule",
                ),
                safety_class="mutate",
                slot_schema=(
                    ("action", "rule-control-action", True),
                    ("target", "rule-name-or-id", True),
                ),
                runtime_intents=(
                    "named-rule-control",
                    "named-rule-confirmation-required",
                ),
            ),
            RouteDescriptor(
                name="device-control",
                priority=900,
                terminal=True,
                matcher=is_control_candidate,
                reason="device writes use the guarded control agent",
                capability_id="device.control",
                mcp_tools=(
                    "hub_list_devices",
                    "hub_get_device",
                    "hub_call_device_command",
                ),
                safety_class="mutate",
                slot_schema=(
                    ("action", "device-command", True),
                    ("target", "device-name-or-id", True),
                    ("value", "command-argument", False),
                ),
            ),
            RouteDescriptor(
                name="hub-logs",
                priority=890,
                terminal=True,
                matcher=is_hub_logs_query,
                reason="log diagnostics read authoritative recent Hubitat hub logs",
                capability_id="diagnostics.hub-logs",
                mcp_tools=("hub_get_logs",),
                runtime_routes=("mcp-fast",),
                runtime_intents=("fallback-hub-logs",),
            ),
            RouteDescriptor(
                name="active-rooms",
                priority=885,
                terminal=True,
                matcher=is_active_rooms_query,
                reason="active rooms use the maintained live dashboard snapshot",
                capability_id="home.active-rooms",
                mcp_tools=("hub_list_devices", "hub_list_rooms"),
                runtime_routes=("mcp-dashboard-active-rooms",),
                runtime_intents=("active-rooms",),
            ),
            RouteDescriptor(
                name="power-accounting",
                priority=880,
                terminal=True,
                matcher=is_power_accounting_query,
                reason="whole-house and monitored-device power are reconciled from live readings",
                capability_id="energy.power-accounting",
                mcp_tools=("hub_list_devices",),
                runtime_routes=("mcp-power-accounting",),
                runtime_intents=("verified-power-accounting",),
            ),
            RouteDescriptor(
                name="octopus-energy",
                priority=875,
                terminal=True,
                matcher=is_octopus_energy_query,
                reason="Octopus reads use live display meters and device evidence",
                capability_id="energy.octopus",
                mcp_tools=("hub_list_devices",),
                slot_schema=(("period", "energy-period", False),),
                runtime_routes=("mcp-fast",),
            ),
            RouteDescriptor(
                name="device-measurement",
                priority=850,
                terminal=True,
                matcher=_measurement_query,
                reason="named device identity and live measurements are authoritative deterministic reads",
                capability_id="device.measurement",
                mcp_tools=("hub_list_devices", "hub_get_device"),
                slot_schema=(
                    ("target", "device-name-or-id", False),
                    ("attribute", "device-attribute", False),
                ),
            ),
            RouteDescriptor(
                name="thermostat-live-state",
                priority=870,
                terminal=True,
                matcher=lambda query: bool(_DIRECT_THERMOSTAT_QUERY.search(query)),
                reason="direct thermostat questions use verified live state",
                capability_id="climate.thermostat-state",
                mcp_tools=("hub_list_devices", "hub_get_device"),
                runtime_routes=("mcp-thermostat-live-state",),
                runtime_intents=("thermostat-live-state",),
            ),
            RouteDescriptor(
                name="named-rule-status",
                priority=865,
                terminal=True,
                matcher=lambda query: _has_match(parse_rule_status_target(query)),
                reason="named rule status resolves one rule and reports live state",
                capability_id="automation.rule-status",
                mcp_tools=("hub_list_rules",),
                slot_schema=(("target", "rule-name-or-id", True),),
                runtime_routes=(
                    "mcp-rule-status",
                    "mcp-rule-status-error",
                    "mcp-rule-status-clarification",
                ),
                runtime_intents=(
                    "automation-rule-status",
                    "automation-rule-status-error",
                    "automation-rule-status-clarification",
                ),
            ),
            RouteDescriptor(
                name="climate-metric-extrema",
                priority=860,
                terminal=True,
                matcher=lambda query: _has_match(_metric_request(query)),
                reason="climate extrema compare validated live room measurements",
                capability_id="climate.metric-extrema",
                mcp_tools=("hub_list_devices",),
                slot_schema=(
                    ("metric", "temperature-or-humidity", True),
                    ("direction", "min-or-max", True),
                ),
                runtime_routes=("mcp-fast",),
                runtime_intents=(
                    "climate-temperature-extreme",
                    "climate-humidity-extreme",
                ),
            ),
            RouteDescriptor(
                name="device-health",
                priority=800,
                terminal=True,
                matcher=is_device_health_query,
                reason="health classifications are live authoritative reads",
                capability_id="health.device",
                mcp_tools=("hub_get_device_health", "hub_list_devices"),
            ),
            RouteDescriptor(
                name="home-attention",
                priority=795,
                terminal=True,
                matcher=is_attention_query,
                reason="attention scans reconcile live health and device evidence",
                capability_id="health.home-attention",
                mcp_tools=("hub_get_device_health", "hub_list_devices"),
                runtime_routes=("mcp-fast", "ai-semantic-home-attention"),
                runtime_intents=("home-attention-summary",),
            ),
            RouteDescriptor(
                name="home-priority",
                priority=790,
                terminal=True,
                matcher=is_home_priority_query,
                reason="priority insights rank verified whole-home evidence",
                capability_id="health.home-priority",
                mcp_tools=(
                    "hub_get_device_health",
                    "hub_get_info",
                    "hub_list_devices",
                ),
                runtime_intents=("home-priority-insight",),
            ),
            RouteDescriptor(
                name="energy-summary",
                priority=700,
                terminal=True,
                matcher=lambda query: bool(_ENERGY_QUERY.search(query)),
                reason="energy summaries use authoritative Octopus/device evidence",
                capability_id="energy.summary",
                mcp_tools=("hub_list_devices",),
            ),
            RouteDescriptor(
                name="automation-recommendation",
                priority=650,
                terminal=True,
                matcher=AutomationRecommendationService.matches,
                reason="recommendations are grounded in the selected live device inventory",
                capability_id="automation.recommendation",
                mcp_tools=("hub_list_devices",),
                runtime_routes=(
                    "ollama+automation-recommendation",
                    "mcp-automation-recommendation-ai-fallback",
                    "mcp-automation-recommendation",
                ),
                runtime_intents=("automation-recommendation",),
            ),
            RouteDescriptor(
                name="home-summary",
                priority=620,
                terminal=True,
                matcher=lambda query: bool(_HOME_SUMMARY_RE.search(query)),
                reason="home summaries synthesize bounded authoritative evidence",
                capability_id="home.summary",
                mcp_tools=("hub_list_devices", "hub_get_info"),
                runtime_routes=("ai-semantic-home-evidence",),
                runtime_intents=("home-summary",),
            ),
            RouteDescriptor(
                name="recent-request-diagnostics",
                priority=610,
                terminal=True,
                matcher=is_recent_log_diagnostics_query,
                reason="explicit HomeBrain request diagnostics read the local trace store",
                capability_id="diagnostics.homebrain-requests",
                runtime_routes=("homebrain-recent-request-diagnostics",),
                runtime_intents=("recent-log-diagnostics",),
            ),
            RouteDescriptor(
                name="ai-evidence",
                priority=500,
                terminal=False,
                matcher=is_ai_evidence_query,
                reason="reasoning questions use bounded authoritative evidence before synthesis",
                capability_id="ai.evidence-synthesis",
                mcp_tools=("hub_search_tools",),
            ),
            RouteDescriptor(
                name="general-assistant",
                priority=100,
                terminal=False,
                matcher=lambda query: bool(query.strip()),
                reason="fallback conversational assistant route",
                capability_id="assistant.general",
            ),
        )
    )


__all__ = ["build_route_registry"]
