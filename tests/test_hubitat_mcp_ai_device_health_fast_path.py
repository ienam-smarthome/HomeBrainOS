from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_health import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from routing import is_fast_path_query  # noqa: E402


class FakeMCP:
    async def list_tools(self):
        return [
            MCPTool(
                name="hub_list_devices",
                description="List devices",
                input_schema={"type": "object", "properties": {}},
            )
        ]

    async def call_tool(self, name, arguments):
        assert name == "hub_list_devices"
        if arguments.get("capabilityFilter") == "Health Check":
            data = {
                "devices": [
                    {
                        "id": "1",
                        "label": "Bedroom Sensor",
                        "attributes": [
                            {"name": "healthStatus", "value": "offline"}
                        ],
                    }
                ]
            }
        elif str(arguments.get("filter", "")).startswith("stale:"):
            data = {
                "devices": [
                    {
                        "id": "1",
                        "label": "Bedroom Sensor",
                        "lastActivity": "2026-07-13T10:00:00Z",
                        "disabled": False,
                    },
                    {
                        "id": "2",
                        "label": "Hallway Motion",
                        "lastActivity": "2026-07-12T10:00:00Z",
                        "disabled": False,
                    },
                    {
                        "id": "3",
                        "label": "Unused Test Device",
                        "lastActivity": "2026-07-01T10:00:00Z",
                        "disabled": True,
                    },
                ]
            }
        else:
            raise AssertionError(arguments)

        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def test_offline_stale_wording_is_fast_path():
    assert is_fast_path_query("List devices that are offline or stale") is True
    assert is_fast_path_query("Show stale devices") is True
    assert is_fast_path_query("Device health") is True


def test_device_health_lists_offline_and_stale_without_duplicates():
    answer = asyncio.run(
        FastFallbackRouter(FakeMCP(), attention_stale_hours=48).answer(
            "List devices that are offline or stale"
        )
    )

    assert answer["success"] is True
    assert answer["display"]["kind"] == "device-health"
    assert answer["display"]["subtitle"] == "2 devices need attention"
    rows = {item["title"]: item for item in answer["display"]["items"]}
    assert rows["Bedroom Sensor"]["value"] == "Offline"
    assert rows["Hallway Motion"]["value"] == "Stale 48h+"
    assert "Unused Test Device" not in rows
    assert answer["message"].count("Bedroom Sensor") == 1
