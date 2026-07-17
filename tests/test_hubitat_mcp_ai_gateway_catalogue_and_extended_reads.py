from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_extended_reads import FastFallbackRouter  # noqa: E402
from fast_fallback_speech import normalise_spoken_device_name  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from mcp_state_broker import MCPStateBroker  # noqa: E402
from mcp_tool_catalogue import build_mcp_tool_catalogue  # noqa: E402
from routing_policy import classify_query  # noqa: E402
from webui import render_page  # noqa: E402


class FakeGatewayClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.server_info = {"name": "Hubitat MCP", "version": "3.4.1"}
        self.configured = True
        self.tools = [
            MCPTool(
                "hub_get_info",
                "Comprehensive hub information",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_apps_code",
                "Read-only gateway: hub_list_apps, hub_list_hpm_packages, hub_list_drivers",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            ),
            MCPTool(
                "hub_manage_code",
                "Write gateway also contains hub_list_apps and hub_create_app",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            ),
            MCPTool(
                "hub_read_diagnostics",
                "Read-only gateway: hub_get_logs, hub_get_performance_stats, hub_get_jobs, hub_get_memory_history, hub_get_radio_details",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            ),
            MCPTool(
                "hub_read_devices",
                "Read-only gateway: hub_list_devices, hub_list_device_events, hub_get_device",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            ),
            MCPTool(
                "hub_read_variables",
                "Read-only gateway: hub_list_variables, hub_get_variable",
                {"type": "object", "properties": {}},
            ),
            MCPTool(
                "hub_read_dashboards",
                "Read-only gateway: hub_list_dashboards, hub_get_dashboard",
                {"type": "object", "properties": {}},
            ),
        ]

    async def initialize(self, force: bool = False) -> None:
        return None

    async def close(self) -> None:
        return None

    async def list_tools(self, refresh: bool = False):
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        self.calls.append((name, arguments))
        hidden = arguments.get("tool") if name.startswith(("hub_read_", "hub_manage_")) else name
        args = arguments.get("args", {}) if name.startswith(("hub_read_", "hub_manage_")) else arguments

        if hidden == "hub_list_apps":
            data = {
                "apps": [
                    {"id": "1", "label": "MCP Rule Server", "status": "enabled"},
                    {"id": "2", "label": "Prayer Times", "status": "enabled"},
                ]
            }
        elif hidden == "hub_get_logs":
            data = {
                "logs": [
                    {
                        "level": "error",
                        "message": "Example device timeout",
                        "date": "2026-07-17T15:00:00Z",
                    }
                ]
            }
        elif hidden == "hub_list_devices":
            data = {
                "devices": [
                    {
                        "id": "101",
                        "label": "Pray times",
                        "room": "Apps",
                        "currentStates": {"status": "available"},
                    }
                ]
            }
        elif hidden == "hub_list_device_events":
            assert args["deviceId"] == "101"
            data = {
                "events": [
                    {
                        "name": "status",
                        "value": "updated",
                        "date": "2026-07-17T14:59:00Z",
                    }
                ]
            }
        else:
            data = {"ok": True, "tool": hidden, "args": args}

        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def test_prayer_times_alias_is_safe_and_exact():
    assert normalise_spoken_device_name("Prayer times") == "pray times"
    assert normalise_spoken_device_name("Pray times") == "pray times"


def test_gateway_read_queries_route_to_mcp_fast():
    for query in (
        "Show hub logs and errors",
        "List installed apps",
        "Show scheduled jobs",
        "Show memory history",
        "Show events for Prayer times",
    ):
        assert classify_query(query).route == "mcp-fast"


def test_hidden_tool_prefers_read_only_gateway_and_is_transparent():
    fake = FakeGatewayClient()
    broker = MCPStateBroker(fake)
    result = asyncio.run(broker.call_tool("hub_list_apps", {"scope": "instances"}))

    assert fake.calls[-1] == (
        "hub_read_apps_code",
        {"tool": "hub_list_apps", "args": {"scope": "instances"}},
    )
    assert result.name == "hub_list_apps"
    assert result.raw["gateway"] == "hub_read_apps_code"
    assert broker.stats()["gateway_translations"] == 1


def test_catalogue_counts_underlying_tools_without_counting_gateways():
    fake = FakeGatewayClient()
    broker = MCPStateBroker(fake)
    catalogue = asyncio.run(build_mcp_tool_catalogue(broker))

    assert catalogue["visible_count"] == len(fake.tools)
    assert catalogue["core_tools"] == ["hub_get_info"]
    assert "hub_list_apps" in catalogue["all_underlying_tools"]
    assert "hub_get_logs" in catalogue["all_underlying_tools"]
    assert catalogue["underlying_count"] > catalogue["core_count"]
    apps_group = next(
        item for item in catalogue["gateways"] if item["gateway"] == "hub_read_apps_code"
    )
    assert "hub_list_apps" in apps_group["tools"]
    assert apps_group["read_only"] is True


def test_installed_apps_and_logs_use_direct_gateway_reads():
    fake = FakeGatewayClient()
    router = FastFallbackRouter(MCPStateBroker(fake), cpu_probe_enabled=False)

    apps = asyncio.run(router.answer("List installed apps"))
    assert apps["success"] is True
    assert apps["intent"] == "fallback-installed-apps"
    assert "MCP Rule Server" in apps["message"]
    assert apps["display"]["metrics"][0]["value"] == "2"

    logs = asyncio.run(router.answer("Show hub logs and errors"))
    assert logs["success"] is True
    assert logs["intent"] == "fallback-hub-logs"
    assert "Example device timeout" in logs["message"]


def test_prayer_times_status_and_events_resolve_selected_device():
    fake = FakeGatewayClient()
    router = FastFallbackRouter(MCPStateBroker(fake), cpu_probe_enabled=False)

    status = asyncio.run(router.answer("Show prayer times"))
    assert status["success"] is True
    assert status["intent"] == "fallback-device-status"
    assert status["device_label"] == "Pray times"

    events = asyncio.run(router.answer("Show events for prayer times"))
    assert events["success"] is True
    assert events["intent"] == "fallback-device-events"
    assert "updated" in events["message"]


def test_web_ui_includes_mcp_tool_catalogue_button():
    page = render_page("Hubitat MCP AI", "0.3.4-alpha")
    assert 'id="mcpToolCatalogue"' in page
    assert "/api/mcp-tool-catalogue" in page
