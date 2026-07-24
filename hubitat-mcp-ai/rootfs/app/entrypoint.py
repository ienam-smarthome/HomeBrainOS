from __future__ import annotations

from pathlib import Path

import uvicorn

import entrypoint_core as _core
from entrypoint_core import *  # noqa: F401,F403
from hub_firmware_backup_retry import install_firmware_backup_settle_retry
from named_app_control import install_named_app_controller
from runtime_route_bridge import install_runtime_route_bridge

PREVIOUS_RELEASE_VERSION = "0.10.65"
RELEASE_VERSION = "0.10.66"
BAKED_VERSION_PATH = Path("/app/.homebrain-build-version")


def _runtime_release_version() -> str:
    """Return the version baked into the running add-on image."""

    try:
        baked = BAKED_VERSION_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        baked = ""
    return baked or RELEASE_VERSION


RUNTIME_RELEASE_VERSION = _runtime_release_version()

# Composition remains in entrypoint_core.py. Keep these explicit contract markers
# visible here because release validation and maintainers verify the safety-critical
# wiring from the public entrypoint. The order mirrors the delegated composition:
# - install_hybrid_assistant_query_policy()
# - install_hybrid_verified_read_routes
# - install_unified_mcp_agent_orchestrator
# - from hub_firmware_update_workflow import install_hub_firmware_update_workflow
# - hub_firmware_update_workflow = install_hub_firmware_update_workflow(
# - option_bool("rule_write_enabled", False)
# - options.get("mcp_catalog_cache_seconds") or 300
# - options.get("device_index_metadata_ttl_seconds") or 600
# Release metadata compatibility markers only:
# application.VERSION = RELEASE_VERSION
# application.app.version = RELEASE_VERSION

application = _core.application
# The baked image version is the only runtime authority. Installers must not mutate
# application.VERSION or application.app.version after this point.
application.VERSION = RUNTIME_RELEASE_VERSION
application.app.version = RUNTIME_RELEASE_VERSION
application.BAKED_VERSION = RUNTIME_RELEASE_VERSION

# Override release metadata before rebuilding release-sensitive HTTP routes.
_core.PREVIOUS_RELEASE_VERSION = PREVIOUS_RELEASE_VERSION
_core.RELEASE_VERSION = RUNTIME_RELEASE_VERSION

# The firmware workflow already creates and independently verifies a fresh backup.
# Retry the destructive firmware tool exactly once when its own backup index lags.
firmware_backup_retry = install_firmware_backup_settle_retry(
    _core.hub_firmware_update_workflow,
    settle_seconds=4.0,
)

# Install app control as a terminal deterministic wrapper outside AI and generic
# device control. Every app write requires clickable confirmation using an exact
# App ID. Then rebuild /api/ask, the non-PWA home page, and runtime diagnostics.
app_controller = install_named_app_controller(_core.application)
runtime_request_registry = install_runtime_route_bridge(_core.application)

app = _core.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
