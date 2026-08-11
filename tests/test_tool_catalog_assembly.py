from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from tool_catalog_assembly import build_request_tool_catalog  # noqa: E402
from tool_discovery_catalog import ToolDiscoveryCatalog  # noqa: E402
from tool_registry import LOCAL_CONTROL_TOOL, LOCAL_FILTER_TOOL  # noqa: E402


def test_local_tools_are_appended_to_remote_tools() -> None:
    catalog = build_request_tool_catalog([])

    assert isinstance(catalog, ToolDiscoveryCatalog)
    assert LOCAL_CONTROL_TOOL in catalog.available_names
    assert LOCAL_FILTER_TOOL in catalog.available_names


def test_remote_tools_are_preserved_alongside_local_tools() -> None:
    class _RemoteTool:
        name = "some_remote_tool"
        description = "A remote tool"
        input_schema: dict = {}

    catalog = build_request_tool_catalog([_RemoteTool()])

    assert "some_remote_tool" in catalog.available_names
    assert LOCAL_CONTROL_TOOL in catalog.available_names


def test_empty_remote_tools_still_yields_full_local_set() -> None:
    catalog = build_request_tool_catalog([])

    # Eleven safe-read tools (added homebrain_location_events in 0.10.410,
    # so the general model loop can reason over location/mode event history
    # now that the deterministic dispatch branch for it is opt-in rather
    # than the only way to reach that data) plus the one control tool.
    assert len(catalog.available_names) == 12
