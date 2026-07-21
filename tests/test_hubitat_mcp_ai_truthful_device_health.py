from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import request_tracing  # noqa: E402
from device_health_fast_route import (  # noqa: E402
    install_device_health_fast_route,
    is_device_health_query,
)
from fast_fallback_device_health import (  # noqa: E402
    FastFallbackRouter,
    classify_age_only_device,
)
from mcp_client import MCPToolResult  # noqa: E402


def device(
    device_id: str,
    label: str,
    states: dict[str, Any],
    *,
    capabilities: list[Any] | None = None,
    last_activity: str = "2026-07-16T12:00:00+01:00",
    disabled: bool = False,
):
    return {
        "id": device_id,
        "name": label,
        "label": label,
        "room": "Test room",
        "disabled": disabled,
        "lastActivity": last_activity,
        "currentStates": states,
        "capabilities": capabilities or [],
    }


def result(rows: list[dict[str, Any]], *, name: str = "hub_list_devices"):
    return MCPToolResult(
        name=name,
        arguments={},
        raw={},
        text="",
        data={"devices": rows},
        is_error=False,
    )


def test_reported_quiet_devices_are_not_promoted_to_stale_faults():
    rows = [
        device("1", "Roborock Q7 Max", {"switch": "on"}, capabilities=["Switch"]),
        device(
            "2",
            "Aqara Mini Switch (Microwave)",
            {"battery": 100},
            capabilities=["Pushable Button", "Battery"],
        ),
        device(
            "3",
            "FP2 Livingroom Sensor",
            {"presence": "not present", "illuminance": 12},
            capabilities=["Presence Sensor", "Illuminance Measurement"],
        ),
        device("4", "LivFP2 socket", {"switch": "on"}, capabilities=["Switch"]),
    ]

    classified = [classify_age_only_device(item) for item in rows]

    assert [item["kind"] for item in classified] == ["quiet", "quiet", "quiet", "quiet"]
    assert all("lastActivity" in item["reason"] or "event-driven" in item["reason"] for item in classified)


def test_periodic_climate_telemetry_can_still_be_stale():
    meter = device(
        "5",
        "Bathroom meter",
        {"temperature": 24.1, "humidity": 55},
        capabilities=["Temperature Measurement", "Relative Humidity Measurement"],
    )

    classified = classify_age_only_device(meter)

    assert classified["kind"] == "stale"
    assert classified["periodic_values"] == {"temperature": 24.1, "humidity": 55}


def test_explicit_health_state_overrides_activity_age():
    socket = device("6", "Bedroom socket", {"switch": "on"}, capabilities=["Switch"])

    assert classify_age_only_device(socket, authoritative_health="online")["kind"] == "quiet"
    assert classify_age_only_device(socket, authoritative_health="offline")["kind"] == "offline"


class FakeHealthRouter(FastFallbackRouter):
    def __init__(self, stale_rows: list[dict[str, Any]], health_rows: list[dict[str, Any]]):
        self.attention_stale_hours = 48.0
        self.stale_rows = stale_rows
        self.health_rows = health_rows

    async def _execute_catalog_tool(
        self,
        direct_tool: str,
        gateway_tool: str,
        arguments: dict[str, Any] | None = None,
    ):
        del direct_tool, gateway_tool
        arguments = arguments or {}
        if arguments.get("filter"):
            return result(self.stale_rows)
        return result(self.health_rows)


def test_health_response_calls_age_only_rows_quiet_not_stale():
    stale_rows = [
        device("1", "Roborock Q7 Max", {"switch": "on"}, capabilities=["Switch"]),
        device(
            "2",
            "Aqara Mini Switch (Microwave)",
            {"battery": 100},
            capabilities=["Pushable Button", "Battery"],
        ),
        device("3", "FP2 Bedroom 3 sensor", {}, capabilities=["Presence Sensor"]),
        device("4", "Bedroom3 PC (MQTT)", {"switch": "on"}, capabilities=["Switch"]),
    ]
    router = FakeHealthRouter(stale_rows, [])

    answer = asyncio.run(router._device_health())

    assert answer["success"] is True
    assert answer["route"] == "mcp-fast"
    assert answer["offline_count"] == 0
    assert answer["stale_telemetry_count"] == 0
    assert answer["quiet_timestamp_count"] == 4
    assert "No devices are confirmed offline or stale" in answer["message"]
    assert answer["display"]["metrics"][0]["value"] == "0"
    assert answer["display"]["metrics"][1]["value"] == "0"
    assert answer["display"]["metrics"][2]["value"] == "4"


def test_negative_health_remains_authoritative_and_periodic_stale_is_separate():
    stale_rows = [
        device(
            "5",
            "Bathroom meter",
            {"temperature": 24.1, "humidity": 55},
            capabilities=["Temperature Measurement", "Relative Humidity Measurement"],
        )
    ]
    health_rows = [
        {
            "id": "9",
            "label": "Failed sensor",
            "attributes": {"healthStatus": "offline"},
        }
    ]
    router = FakeHealthRouter(stale_rows, health_rows)

    answer = asyncio.run(router._device_health())

    assert answer["offline_count"] == 1
    assert answer["stale_telemetry_count"] == 1
    assert answer["quiet_timestamp_count"] == 0
    assert "Failed sensor" in answer["message"]
    assert "Bathroom meter" in answer["message"]


def test_oversized_live_inventory_marks_health_scan_incomplete():
    class OversizedHealthRouter(FakeHealthRouter):
        async def _execute_catalog_tool(
            self,
            direct_tool: str,
            gateway_tool: str,
            arguments: dict[str, Any] | None = None,
        ):
            del direct_tool, gateway_tool
            arguments = arguments or {}
            if arguments.get("filter"):
                return result([])
            return MCPToolResult(
                name="hub_list_devices",
                arguments=arguments,
                raw={},
                text="",
                data={
                    "response_too_large": True,
                    "truncated": True,
                    "estimatedBytes": 125248,
                    "sizeLimitBytes": 120000,
                    "tool": "hub_list_devices",
                },
                is_error=False,
            )

    answer = asyncio.run(OversizedHealthRouter([], [])._device_health())

    assert answer["success"] is False
    assert answer["offline_count"] == 0
    assert answer["stale_telemetry_count"] == 0
    assert "scan was incomplete" in answer["message"]
    assert "cannot confirm that no devices are offline or stale" in answer["message"]
    assert "coverage" in answer["message"]
    assert answer["display"]["subtitle"] == "Scan incomplete"


def test_live_health_inventory_aggregates_all_pages():
    health_rows = [
        device(str(index), f"Sensor {index}", {"healthStatus": "online"})
        for index in range(1, 76)
    ]

    class PagedHealthRouter(FakeHealthRouter):
        def __init__(self):
            super().__init__([], health_rows)
            self.offsets: list[int] = []

        async def _execute_catalog_tool(
            self,
            direct_tool: str,
            gateway_tool: str,
            arguments: dict[str, Any] | None = None,
        ):
            del direct_tool, gateway_tool
            arguments = arguments or {}
            if arguments.get("filter"):
                return result([])
            offset = int(arguments.get("offset") or 0)
            limit = int(arguments.get("limit") or 50)
            self.offsets.append(offset)
            return MCPToolResult(
                name="hub_list_devices",
                arguments=arguments,
                raw={},
                text="",
                data={
                    "devices": health_rows[offset : offset + limit],
                    "total": len(health_rows),
                },
                is_error=False,
            )

    router = PagedHealthRouter()
    answer = asyncio.run(router._device_health())

    assert router.offsets == [0, 50]
    assert answer["success"] is True
    assert '"selected_devices_scanned": 75' in answer["technical"]
    assert answer["offline_count"] == 0


def test_repeated_page_marks_health_scan_incomplete():
    page = [
        device(str(index), f"Sensor {index}", {"healthStatus": "online"})
        for index in range(1, 51)
    ]

    class OffsetIgnoringHealthRouter(FakeHealthRouter):
        async def _execute_catalog_tool(
            self,
            direct_tool: str,
            gateway_tool: str,
            arguments: dict[str, Any] | None = None,
        ):
            del direct_tool, gateway_tool
            arguments = arguments or {}
            if arguments.get("filter"):
                return result([])
            return MCPToolResult(
                name="hub_list_devices",
                arguments=arguments,
                raw={},
                text="",
                data={"devices": page},
                is_error=False,
            )

    answer = asyncio.run(OffsetIgnoringHealthRouter([], page)._device_health())

    assert answer["success"] is False
    assert "scan was incomplete" in answer["message"]
    assert '"selected_devices_scanned": 50' in answer["technical"]


def test_common_question_forms_use_health_fast_route():
    assert is_device_health_query("Are any devices offline or stale?")
    assert is_device_health_query("Do I have stale devices?")
    assert is_device_health_query("Which devices are offline?")
    assert is_device_health_query("Device health status")
    assert not is_device_health_query("Why is the bathroom sensor offline?")


def test_fast_route_bypasses_ai_and_patches_trace_decision():
    class Fallback:
        async def _device_health(self):
            return {
                "success": True,
                "route": "fallback",
                "intent": "fallback-device-health",
                "message": "No devices are confirmed offline or stale.",
            }

    class Application:
        def __init__(self):
            self.fallback = Fallback()

            async def original(_request: Any):
                raise AssertionError("The AI path must not receive a device-health question")

            self.ask = original

    application = Application()
    original_classifier = request_tracing.classify_query
    try:
        install_device_health_fast_route(application)
        answer = asyncio.run(
            application.ask(SimpleNamespace(query="Are any devices offline or stale?"))
        )
        decision = request_tracing.classify_query("Are any devices offline or stale?")
    finally:
        request_tracing.classify_query = original_classifier

    assert answer["route"] == "mcp-fast"
    assert answer["model"] is None
    assert answer["answered_by"] == "Deterministic Hubitat device-health classifier"
    assert decision.route == "mcp-fast"
    assert "event age alone" in decision.reason
