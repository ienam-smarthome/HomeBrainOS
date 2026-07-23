from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from mcp_state_broker import MCPStateBroker  # noqa: E402
from request_tracing import install_request_tracing  # noqa: E402
from webui import render_page  # noqa: E402


class FakeMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.command_count = 0
        self._initialized = False
        self.configured = True
        self.server_info = {"name": "fake"}

    async def initialize(self, force: bool = False) -> None:
        self._initialized = True

    async def close(self) -> None:
        return None

    async def list_tools(self, refresh: bool = False):
        return [
            MCPTool(
                name="hub_list_devices",
                description="List selected devices",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="hub_call_device_command",
                description="Call a device command",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None = None) -> MCPToolResult:
        arguments = dict(arguments or {})
        self.calls.append((name, arguments))
        if name == "hub_list_devices":
            await asyncio.sleep(0.02)
            data = {
                "devices": [
                    {
                        "id": "1",
                        "label": "Bedroom 1 Light",
                        "currentStates": {
                            "switch": "on" if self.command_count else "off"
                        },
                    }
                ]
            }
        elif name == "hub_call_device_command":
            self.command_count += 1
            data = {"success": True}
        else:
            data = {"success": True}
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def test_identical_reads_are_coalesced_and_cached():
    async def scenario():
        raw = FakeMCP()
        broker = MCPStateBroker(raw, device_ttl_seconds=30)
        args = {"detailed": False, "format": "summary"}
        first, second = await asyncio.gather(
            broker.call_tool("hub_list_devices", args),
            broker.call_tool("hub_list_devices", args),
        )
        third = await broker.call_tool("hub_list_devices", args)

        assert first.data == second.data == third.data
        assert [name for name, _args in raw.calls].count("hub_list_devices") == 1
        stats = broker.stats()
        assert stats["misses"] == 1
        assert stats["coalesced"] == 1
        assert stats["hits"] == 1

    asyncio.run(scenario())


def test_device_field_order_does_not_fragment_inventory_cache():
    async def scenario():
        raw = FakeMCP()
        broker = MCPStateBroker(raw, device_ttl_seconds=30)

        await broker.call_tool(
            "hub_list_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": ["label", "id", "currentStates"],
            },
        )
        await broker.call_tool(
            "hub_list_devices",
            {
                "detailed": False,
                "format": "summary",
                "fields": ["currentStates", "label", "id"],
            },
        )

        device_calls = [
            arguments for name, arguments in raw.calls
            if name == "hub_list_devices"
        ]
        assert len(device_calls) == 1
        assert device_calls[0]["fields"] == ["label", "id", "currentStates"]
        assert broker.stats()["hits"] == 1

    asyncio.run(scenario())


def test_inventory_filters_remain_separate_cache_entries():
    async def scenario():
        raw = FakeMCP()
        broker = MCPStateBroker(raw, device_ttl_seconds=30)
        base = {
            "detailed": False,
            "format": "summary",
            "fields": ["id", "label"],
        }

        await broker.call_tool("hub_list_devices", base)
        await broker.call_tool(
            "hub_list_devices",
            {**base, "filter": "stale:48"},
        )
        await broker.call_tool(
            "hub_list_devices",
            {**base, "capabilityFilter": "Health Check"},
        )

        assert [name for name, _args in raw.calls].count("hub_list_devices") == 3
        assert broker.stats()["misses"] == 3

    asyncio.run(scenario())


def test_device_write_invalidates_cached_state_before_verification_read():
    async def scenario():
        raw = FakeMCP()
        broker = MCPStateBroker(raw, device_ttl_seconds=30)
        args = {"detailed": False, "format": "summary"}

        before = await broker.call_tool("hub_list_devices", args)
        assert before.data["devices"][0]["currentStates"]["switch"] == "off"

        await broker.call_tool(
            "hub_call_device_command",
            {"deviceId": "1", "command": "on", "params": []},
        )
        after = await broker.call_tool("hub_list_devices", args)

        assert after.data["devices"][0]["currentStates"]["switch"] == "on"
        assert [name for name, _args in raw.calls].count("hub_list_devices") == 2
        assert broker.stats()["invalidations"] >= 1

    asyncio.run(scenario())


def test_request_trace_attaches_route_cache_and_tool_timings():
    async def scenario():
        raw = FakeMCP()
        broker = MCPStateBroker(raw, device_ttl_seconds=30)

        async def ask(request):
            await broker.call_tool(
                "hub_list_devices",
                {"detailed": False, "format": "summary"},
            )
            return {
                "success": True,
                "route": "mcp-fast",
                "message": "Bedroom 1 Light is off.",
                "agent_orchestrator": "unified-mcp-ai-first",
                "tool_policy_corrected": True,
                "tools_used": [
                    {
                        "name": "homebrain_search_devices",
                        "success": True,
                        "preview": "sensitive payload omitted from diagnostics",
                        "evidence": {
                            "inventory_count": 12,
                            "match_count": 1,
                            "search_strategy": "unprojected-inventory-fallback",
                        },
                    }
                ],
            }

        application = SimpleNamespace(app=FastAPI(), ask=ask)
        store = install_request_tracing(application, broker, limit=10)
        request = SimpleNamespace(query="Which lights are on?")
        answer = await application.ask(request)

        assert answer["performance"]["route_selected"] == "mcp-fast"
        assert answer["performance"]["final_route"] == "mcp-fast"
        assert answer["performance"]["mcp_calls"] == 1
        assert answer["performance"]["cache_misses"] == 1
        assert "Request performance" in answer["technical"]
        assert "Agent execution" in answer["technical"]
        assert '"match_count": 1' in answer["technical"]
        assert '"tool_policy_corrected": true' in answer["technical"]
        assert "sensitive payload omitted" not in answer["technical"]
        recent = store.response()
        assert recent["count"] == 1
        assert recent["requests"][0]["query"] == "Which lights are on?"

    asyncio.run(scenario())


def test_webui_exposes_cache_and_recent_request_diagnostics():
    page = render_page("Hubitat MCP AI", "0.3.0-alpha")
    assert 'id="recentRequests"' in page
    assert 'id="clearMcpCache"' in page
    assert "fetch('/api/recent-requests')" in page
    assert "fetch('/api/mcp-cache')" in page
    assert "State cache" in page
