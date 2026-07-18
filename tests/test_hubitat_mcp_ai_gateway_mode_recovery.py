from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from mcp_state_broker_adaptive import AdaptiveGatewayMCPStateBroker  # noqa: E402


class SwitchingClient:
    configured = True
    server_info: dict[str, Any] = {}

    def __init__(self) -> None:
        self.flat = False
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.refreshes = 0

    async def initialize(self, force: bool = False) -> None:
        return None

    async def list_tools(self, refresh: bool = False):
        if refresh:
            self.refreshes += 1
            self.flat = True
        if self.flat:
            return [
                MCPTool(
                    "hub_list_devices",
                    "List selected devices directly",
                    {"type": "object", "properties": {}},
                )
            ]
        return [
            MCPTool(
                "hub_read_devices",
                "Gateway containing hub_list_devices and hub_get_device",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_read_devices":
            data = {
                "isError": True,
                "error": (
                    "Gateway tool 'hub_read_devices' is disabled — useGateways is OFF "
                    "in this server's preferences."
                ),
                "hint": "Call the underlying tool directly: hub_list_devices. Refresh tools/list to see the flat catalog.",
            }
            return MCPToolResult(
                name=name,
                arguments=args,
                raw={"isError": True},
                text=str(data),
                data=data,
                is_error=True,
            )
        if name == "hub_list_devices":
            data = {"devices": [{"id": "1", "label": "Hallway Motion"}]}
            return MCPToolResult(
                name=name,
                arguments=args,
                raw={},
                text="",
                data=data,
                is_error=False,
            )
        raise AssertionError(f"Unexpected tool call: {name}")


class StaticGatewayClient(SwitchingClient):
    async def list_tools(self, refresh: bool = False):
        return await super().list_tools(refresh=False)


def test_stale_gateway_catalog_refreshes_and_retries_direct_tool():
    client = SwitchingClient()
    broker = AdaptiveGatewayMCPStateBroker(client, device_ttl_seconds=12)

    result = asyncio.run(
        broker.call_tool(
            "hub_list_devices",
            {"detailed": False, "format": "summary"},
        )
    )

    assert result.is_error is False
    assert result.data["devices"][0]["label"] == "Hallway Motion"
    assert client.refreshes == 1
    assert [name for name, _ in client.calls] == [
        "hub_read_devices",
        "hub_list_devices",
    ]
    assert result.raw["gatewayModeRecovered"] is True
    assert result.raw["rejectedGateway"] == "hub_read_devices"


def test_unrelated_gateway_error_is_not_retried():
    class OtherErrorClient(SwitchingClient):
        async def call_tool(self, name: str, arguments=None):
            args = dict(arguments or {})
            self.calls.append((name, args))
            return MCPToolResult(
                name=name,
                arguments=args,
                raw={"isError": True},
                text="Permission denied",
                data={"isError": True, "error": "Permission denied"},
                is_error=True,
            )

    client = OtherErrorClient()
    broker = AdaptiveGatewayMCPStateBroker(client)
    result = asyncio.run(broker.call_tool("hub_list_devices", {}))

    assert result.is_error is True
    assert client.refreshes == 0
    assert [name for name, _ in client.calls] == ["hub_read_devices"]


def test_release_metadata_is_0421():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "version: '0.4.21-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.21-alpha"' in entrypoint
    assert "AdaptiveGatewayMCPStateBroker" in (
        APP_DIR / "device_index_broker.py"
    ).read_text(encoding="utf-8")
