from __future__ import annotations

import uvicorn

import entrypoint_core as _core
from entrypoint_core import *  # noqa: F401,F403
from active_rooms_route import build_active_rooms_terminal_route
from ai_evidence_climate_guard import install_climate_measurement_guard
from answer_guard_registry import AnswerGuardRegistry
from climate_metric_extrema_route import build_climate_metric_extrema_route
from execution_contract_bridge import execution_contract_guard
from final_read_terminal_routes import (
    build_control_focus_octopus_energy,
    build_device_health_fast_route,
    build_hub_logs_route,
)
from home_summary_consistency_guard import build_home_summary_consistency_guard
from hub_firmware_backup_retry import install_firmware_backup_settle_retry
from hub_health_display_bridge import hub_health_display_guard
from named_app_control import install_named_app_controller
from named_entity_resolution_adapters import install_named_entity_resolution_adapters
from named_rule_disable_guard import install_named_rule_disable_guard
from named_rule_status_route import build_named_rule_status_terminal_route
from power_device_discovery_fallback import install_power_device_discovery_fallback
from recent_log_diagnostics_route import build_recent_log_diagnostics_terminal_route
from release_version import (
    BAKED_VERSION_PATH,
    PREVIOUS_RELEASE_VERSION,
    RELEASE_VERSION,
    runtime_release_version,
)
from request_composition import AskCompositionBuilder
from route_shadow_observer import install_route_shadow_observer
from runtime_route_bridge import install_runtime_route_bridge
from semantic_attention_reconciliation import wrap_semantic_home_query_route
from semantic_home_query_registry import build_semantic_home_query_terminal_route
from semantic_home_summary_registry import build_semantic_home_summary_terminal_route
from shared_power_summary_bridge import install_shared_power_summary_bridge
from structured_health_contract import install_structured_health_contract
from thermostat_summary_registry import (
    build_thermostat_summary_guard,
    build_thermostat_terminal_route,
)


def _runtime_release_version() -> str:
    """Compatibility wrapper around the shared release-version resolver."""

    return runtime_release_version(BAKED_VERSION_PATH)


RUNTIME_RELEASE_VERSION = _runtime_release_version()

# Composition remains in entrypoint_core.py. Keep these explicit contract markers
# visible here because release validation and maintainers verify the safety-critical
# wiring from the public entrypoint.
# - install_hybrid_assistant_query_policy()
# - install_hybrid_verified_read_routes
# - build_unified_mcp_agent_handler
# - application.ask = compose_ask_layers(...)
# - compatibility API: install_unified_mcp_agent_orchestrator
# - from hub_firmware_update_workflow import install_hub_firmware_update_workflow
# - hub_firmware_update_workflow = install_hub_firmware_update_workflow(
# - option_bool("rule_write_enabled", False)
# - options.get("mcp_catalog_cache_seconds") or 300
# - options.get("device_index_metadata_ttl_seconds") or 600
# application.VERSION = RELEASE_VERSION
# application.app.version = RELEASE_VERSION

application = _core.application
application.VERSION = RUNTIME_RELEASE_VERSION
application.app.version = RUNTIME_RELEASE_VERSION
application.BAKED_VERSION = RUNTIME_RELEASE_VERSION
_core.PREVIOUS_RELEASE_VERSION = PREVIOUS_RELEASE_VERSION
_core.RELEASE_VERSION = RUNTIME_RELEASE_VERSION

power_device_discovery_fallback = install_power_device_discovery_fallback()
shared_power_summary_bridge = install_shared_power_summary_bridge()
structured_health_reader = install_structured_health_contract(_core.application)

climate_measurement_guard = install_climate_measurement_guard(
    _core.ai_evidence_planner,
)

firmware_backup_retry = install_firmware_backup_settle_retry(
    _core.hub_firmware_update_workflow,
    settle_seconds=4.0,
)

named_rule_disable_guard = install_named_rule_disable_guard(
    _core.named_rule_controller,
)
auxiliary_request_layers = AskCompositionBuilder(
    _core.application,
    base_name="core-request-stack",
)
app_controller = auxiliary_request_layers.capture(
    "named-app-control",
    lambda: install_named_app_controller(_core.application),
)
named_entity_resolver = install_named_entity_resolution_adapters(
    app_controller=app_controller,
    rule_controller=_core.named_rule_controller,
)
hub_health_guard_registry = AnswerGuardRegistry(_core.application)
hub_health_guard_registry.register_guard(
    "hub-health-display",
    hub_health_display_guard,
)
hub_health_display_bridge = auxiliary_request_layers.capture(
    "hub-health-display-registry",
    hub_health_guard_registry.install,
)
semantic_home_registry = AnswerGuardRegistry(_core.application)
semantic_home_registry.register_terminal_route(
    "recent-log-diagnostics",
    build_recent_log_diagnostics_terminal_route(
        _core.application,
        _core.request_traces,
    ),
)
semantic_home_registry.register_terminal_route(
    "semantic-home-summary",
    build_semantic_home_summary_terminal_route(
        _core.application,
        _core.home_snapshot,
    ),
)
semantic_home_registry.register_terminal_route(
    "semantic-home-query",
    wrap_semantic_home_query_route(
        build_semantic_home_query_terminal_route(_core.application)
    ),
)
semantic_home_routes = auxiliary_request_layers.capture(
    "semantic-home-registry",
    semantic_home_registry.install,
)
summary_thermostat_registry = AnswerGuardRegistry(_core.application)
summary_thermostat_registry.register_terminal_route(
    "thermostat-live-state",
    build_thermostat_terminal_route(_core.application),
)
summary_thermostat_registry.register_guard(
    "home-summary-consistency",
    build_home_summary_consistency_guard(_core.application),
)
summary_thermostat_registry.register_guard(
    "thermostat-summary",
    build_thermostat_summary_guard(_core.application),
)
summary_thermostat_routes = auxiliary_request_layers.capture(
    "summary-thermostat-registry",
    summary_thermostat_registry.install,
)
read_execution_registry = AnswerGuardRegistry(_core.application)
read_execution_registry.register_terminal_route(
    "hub-logs",
    build_hub_logs_route(_core.application),
)
read_execution_registry.register_terminal_route(
    "active-rooms",
    build_active_rooms_terminal_route(
        _core.application,
        _core.dashboard_snapshot,
    ),
)
read_execution_registry.register_terminal_route(
    "device-health-fast-route",
    build_device_health_fast_route(_core.application),
)
read_execution_registry.register_terminal_route(
    "control-focus-octopus-energy",
    build_control_focus_octopus_energy(_core.application),
)
read_execution_registry.register_terminal_route(
    "named-rule-status",
    build_named_rule_status_terminal_route(_core.named_rule_controller),
)
read_execution_registry.register_terminal_route(
    "climate-metric-extrema",
    build_climate_metric_extrema_route(_core.semantic_metric_comparison),
)
read_execution_registry.register_guard(
    "execution-contract",
    execution_contract_guard,
)
read_execution_routes = auxiliary_request_layers.capture(
    "read-execution-registry",
    read_execution_registry.install,
)
auxiliary_request_handler = auxiliary_request_layers.finalize()
route_shadow_observer = install_route_shadow_observer(
    _core.application,
    _core.application.route_registry,
    limit=500,
)
runtime_request_registry = install_runtime_route_bridge(_core.application)

app = _core.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
