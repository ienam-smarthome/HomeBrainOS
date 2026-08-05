"""Assembles the per-request tool catalog from remote and local tools.

Extracted from `mcp_agent_orchestrator.UnifiedMCPAgent._process_user_request`,
where this was a straight-line, side-effect-free block: given the remote
tools already fetched for a request, append the fixed set of local
(deterministic) tools and hand back a ready `ToolDiscoveryCatalog`. Kept as
its own module so the request loop doesn't have to inline eleven local-tool
constructors every time it's read.
"""

from __future__ import annotations

from tool_discovery_catalog import ToolDiscoveryCatalog
from tool_registry import (
    active_lights_tool,
    active_rooms_tool,
    active_switches_tool,
    control_devices_tool,
    device_history_tool,
    device_filter_tool,
    device_query_tool,
    device_resolver_tool,
    home_snapshot_tool,
    hub_info_tool,
    weather_snapshot_tool,
)


def build_request_tool_catalog(remote_tools: list) -> ToolDiscoveryCatalog:
    """Combine already-fetched remote tools with the fixed local tool set.

    `remote_tools` should already be limited to the per-agent tool cap
    before this is called; this function only appends the local
    (deterministic, non-remote) tools and constructs the catalog.
    """

    safe_read_tools = [
        device_filter_tool(),
        device_query_tool(),
        device_resolver_tool(),
        device_history_tool(),
        active_lights_tool(),
        active_rooms_tool(),
        active_switches_tool(),
        home_snapshot_tool(),
        hub_info_tool(),
        weather_snapshot_tool(),
    ]
    all_tools = [*remote_tools, *safe_read_tools, control_devices_tool()]
    return ToolDiscoveryCatalog(all_tools)


__all__ = ["build_request_tool_catalog"]
