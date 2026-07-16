from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_attention import FastFallbackRouter  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402


class FakeMCP:
    async def list_tools(self):
        return [
            MCPTool(
                name="hub_list_devices",
                description="List devices",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPTool(
                name="hub_get_info",
                description="Hub information",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name, arguments):
        if name == "hub_get_info":
            assert arguments == {
                "includeAppUpdate": True,
                "includeHealthAlerts": True,
            }
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="",
                data={
                    "name": "Hub C8 Pro",
                    "firmwareVersion": "2.5.1.128",
                    "platformUpdate": {
                        "available": True,
                        "currentVersion": "2.5.1.128",
                        "availableVersion": "2.5.1.129",
                    },
                    "appUpdate": {
                        "installedVersion": "3.4.0",
                        "latestVersion": "3.4.0",
                        "updateAvailable": False,
                    },
                },
                is_error=False,
            )

        assert name == "hub_list_devices"
        capability = arguments.get("capabilityFilter")
        if capability == "Battery":
            data = {
                "devices": [
                    {
                        "id": "1",
                        "label": "Livingroom TRV",
                        "currentStates": {"battery": 12},
                    },
                    {
                        "id": "2",
                        "label": "Fridge Door",
                        "currentStates": {"battery": 17},
                    },
                    {
                        "id": "3",
                        "label": "Hallway Motion",
                        "currentStates": {"battery": 66},
                    },
                ]
            }
        elif capability == "Health Check":
            data = {
                "devices": [
                    {
                        "id": "4",
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
                        "id": "4",
                        "label": "Bedroom Sensor",
                        "lastActivity": "2026-07-13T10:00:00Z",
                        "disabled": False,
                    },
                    {
                        "id": "5",
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


def test_attention_uses_same_live_batteries_as_low_battery_answer():
    answer = asyncio.run(
        FastFallbackRouter(FakeMCP(), attention_stale_hours=48).answer(
            "what needs attention"
        )
    )

    assert answer["success"] is True
    assert answer["display"]["kind"] == "attention"
    assert answer["display"]["subtitle"] == "4 issues found"

    rows = {item["title"]: item for item in answer["display"]["items"]}
    assert rows["Livingroom TRV"]["value"] == "12%"
    assert rows["Fridge Door"]["value"] == "17%"
    assert rows["Bedroom Sensor"]["value"] == "Offline"
    assert rows["Hub platform update"]["value"] == "2.5.1.129"
    assert "Unused Test Device" not in rows

    metrics = {
        item["label"]: item["value"]
        for item in answer["display"]["metrics"]
    }
    assert metrics == {
        "Low batteries": "2",
        "Offline/stale": "1",
        "Hub warnings": "0",
        "Updates": "1",
    }
    assert "No low-battery or offline devices" not in answer["message"]


class FailedBatteryMCP(FakeMCP):
    async def call_tool(self, name, arguments):
        if name == "hub_list_devices" and arguments.get("capabilityFilter") == "Battery":
            return MCPToolResult(
                name=name,
                arguments=arguments,
                raw={},
                text="Battery lookup failed",
                data={},
                is_error=True,
            )
        return await super().call_tool(name, arguments)


def test_attention_never_claims_zero_when_a_source_failed():
    answer = asyncio.run(
        FastFallbackRouter(FailedBatteryMCP()).answer("attention")
    )
    titles = [item["title"] for item in answer["display"]["items"]]
    assert "Attention scan incomplete" in titles
    assert "battery" in answer["display"]["note"]
