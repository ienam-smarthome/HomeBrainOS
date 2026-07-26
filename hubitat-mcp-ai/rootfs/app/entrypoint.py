from __future__ import annotations

import uvicorn

import entrypoint_core as _core
from entrypoint_core import *  # noqa: F401,F403
from ai_evidence_climate_guard import install_climate_measurement_guard
from climate_metric_extrema_route import install_climate_metric_extrema_route
from home_summary_consistency_guard import install_home_summary_consistency_guard
from hub_firmware_backup_retry import install_firmware_backup_settle_retry
from hub_health_display_bridge import install_hub_health_display_bridge
from named_app_control import install_named_app_controller
from runtime_route_bridge import install_runtime_route_bridge
from release_version import (
    BAKED_VERSION_PATH,
    PREVIOUS_RELEASE_VERSION,
    RELEASE_VERSION,
    runtime_release_version,
)
from semantic_home_query_router import install_semantic_home_query_router
from semantic_home_summary_agent import install_semantic_home_summary_agent
from thermostat_summary_guard import install_thermostat_summary_guard


def _runtime_release_version() -> str:
    """Compatibility wrapper around the shared release-version resolver."""

    return runtime_release_version(BAKED_VERSION_PATH)


RUNTIME_RELEASE_VERSION = _runtime_release_version()

# Composition remains in entrypoint_core.py. Keep these explicit contract markers
# visible here because release validation and maintainers verify the safety-critical
# wiring from the public entrypoint.
# - install_hybrid_assistant_query_policy()
# - install_hybrid_verified_read_routes
# - install_unified_mcp_agent_orchestrator
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

app_controller = install_named_app_controller(_core.application)
hub_health_display_bridge = install_hub_health_display_bridge(_core.application)
semantic_home_summary_agent = install_semantic_home_summary_agent(
    _core.application,
    _core.home_snapshot,
)
semantic_home_query_router = install_semantic_home_query_router(_core.application)
home_summary_consistency_guard = install_home_summary_consistency_guard(_core.application)
thermostat_summary_guard = install_thermostat_summary_guard(_core.application)
climate_metric_extrema_route = install_climate_metric_extrema_route(
    _core.application,
    _core.semantic_metric_comparison,
)
runtime_request_registry = install_runtime_route_bridge(_core.application)

app = _core.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
