from __future__ import annotations

import uvicorn

import entrypoint_core as _core
from entrypoint_core import *  # noqa: F401,F403
from ai_evidence_climate_guard import install_climate_measurement_guard
from answer_guard_registry import AnswerGuardRegistry
from climate_metric_extrema_route import build_climate_metric_extrema_route
from execution_contract_bridge import execution_contract_guard
from home_summary_consistency_guard import build_home_summary_consistency_guard
from hub_firmware_backup_retry import install_firmware_backup_settle_retry
from hub_health_display_bridge import hub_health_display_guard
from named_app_control import install_named_app_controller
from named_entity_resolution_adapters import install_named_entity_resolution_adapters
from named_rule_disable_guard import install_named_rule_disable_guard
from named_rule_status_route import build_named_rule_status_terminal_route
from runtime_route_bridge import install_runtime_route_bridge
from release_version import (
    BAKED_VERSION_PATH,
    PREVIOUS_RELEASE_VERSION,
    RELEASE_VERSION,
    runtime_release_version,
)
from request_composition import AskCompositionBuilder
from semantic_home_query_registry import build_semantic_home_query_terminal_route
from semantic_home_summary_agent import install_semantic_home_summary_agent
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
semantic_home_summary_agent = auxiliary_request_layers.capture(
    "semantic-home-summary",
    lambda: install_semantic_home_summary_agent(
        _core.application,
        _core.home_snapshot,
    ),
)
semantic_home_query_registry = AnswerGuardRegistry(_core.application)
semantic_home_query_registry.register_terminal_route(
    "semantic-home-query",
    build_semantic_home_query_terminal_route(_core.application),
)
semantic_home_query_router = auxiliary_request_layers.capture(
    "semantic-home-query-registry",
    semantic_home_query_registry.install,
)
home_summary_guard_registry = AnswerGuardRegistry(_core.application)
home_summary_guard_registry.register_guard(
    "home-summary-consistency",
    build_home_summary_consistency_guard(_core.application),
)
home_summary_consistency_guard = auxiliary_request_layers.capture(
    "home-summary-guard-registry",
    home_summary_guard_registry.install,
)
thermostat_guard_registry = AnswerGuardRegistry(_core.application)
thermostat_guard_registry.register_terminal_route(
    "thermostat-live-state",
    build_thermostat_terminal_route(_core.application),
)
thermostat_guard_registry.register_guard(
    "thermostat-summary",
    build_thermostat_summary_guard(_core.application),
)
thermostat_summary_guard = auxiliary_request_layers.capture(
    "thermostat-guard-registry",
    thermostat_guard_registry.install,
)
climate_extrema_registry = AnswerGuardRegistry(_core.application)
climate_extrema_registry.register_terminal_route(
    "climate-metric-extrema",
    build_climate_metric_extrema_route(_core.semantic_metric_comparison),
)
climate_metric_extrema_route = auxiliary_request_layers.capture(
    "climate-extrema-registry",
    climate_extrema_registry.install,
)
named_rule_status_registry = AnswerGuardRegistry(_core.application)
named_rule_status_registry.register_terminal_route(
    "named-rule-status",
    build_named_rule_status_terminal_route(_core.named_rule_controller),
)
named_rule_status_route = auxiliary_request_layers.capture(
    "named-rule-status-registry",
    named_rule_status_registry.install,
)
answer_guard_registry = AnswerGuardRegistry(_core.application)
answer_guard_registry.register_guard(
    "execution-contract",
    execution_contract_guard,
)
execution_contract_bridge = auxiliary_request_layers.capture(
    "answer-guard-registry",
    answer_guard_registry.install,
)
runtime_request_registry = auxiliary_request_layers.capture(
    "runtime-route-bridge",
    lambda: install_runtime_route_bridge(_core.application),
)
auxiliary_request_handler = auxiliary_request_layers.finalize()

app = _core.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
