from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_health import FastFallbackRouter  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


def device(
    device_id: str,
    label: str,
    *,
    states: dict[str, Any] | None = None,
    attributes: dict[str, Any] | list[dict[str, Any]] | None = None,
    capabilities: list[Any] | None = None,
    last_activity: str = "2026-07-17T12:00:00+01:00",
):
    return {
        "id": device_id,
        "name": label,
        "label": label,
        "room": "Test room",
        "disabled": False,
        "lastActivity": last_activity,
        "currentStates": states or {},
        "attributes": attributes or {},
        "capabilities": capabilities or [],
    }


def result(rows: list[dict[str, Any]]) -> MCPToolResult:
    return MCPToolResult(
        name="hub_list_devices",
        arguments={},
        raw={},
        text="",
        data={"devices": rows},
        is_error=False,
    )


class FakeLiveHealthRouter(FastFallbackRouter):
    def __init__(
        self,
        stale_rows: list[dict[str, Any]],
        live_rows: list[dict[str, Any]],
    ) -> None:
        self.attention_stale_hours = 48.0
        self.stale_rows = stale_rows
        self.live_rows = live_rows
        self.calls: list[dict[str, Any]] = []

    async def _execute_catalog_tool(
        self,
        direct_tool: str,
        gateway_tool: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        del direct_tool, gateway_tool
        arguments = dict(arguments or {})
        self.calls.append(arguments)
        if arguments.get("filter"):
            return result(self.stale_rows)
        return result(self.live_rows)


def test_live_healthstatus_from_all_selected_devices_overrides_empty_stale_rows():
    stale_rows = [
        device(
            "1",
            "Roborock Q7 Max",
            capabilities=["Actuator", "Switch"],
        ),
        device(
            "2",
            "🔢 Tuya Remote (bedroom 3)",
            capabilities=["PushableButton", "HealthCheck"],
        ),
        device(
            "3",
            "Generic outlet",
            capabilities=["Switch", "HealthCheck"],
        ),
        device(
            "4",
            "FP2 Livingroom Sensor",
            capabilities=["PresenceSensor"],
        ),
    ]
    live_rows = [
        device(
            "1",
            "Roborock Q7 Max",
            states={"healthStatus": "offline", "status": "clear", "switch": "on"},
            capabilities=["Actuator", "Switch"],
        ),
        device(
            "2",
            "🔢 Tuya Remote (bedroom 3)",
            states={"healthStatus": "offline", "Status": "clear", "battery": 100},
            capabilities=["PushableButton", "HealthCheck"],
        ),
        device(
            "3",
            "Generic outlet",
            attributes=[
                {"name": "healthStatus", "currentValue": "offline"},
                {"name": "switch", "currentValue": "off"},
            ],
            capabilities=["Switch", "HealthCheck"],
        ),
        device(
            "4",
            "FP2 Livingroom Sensor",
            states={"presence": "not present", "healthStatus": "online"},
            capabilities=["PresenceSensor"],
        ),
    ]
    router = FakeLiveHealthRouter(stale_rows, live_rows)

    answer = asyncio.run(router._device_health())

    assert answer["success"] is True
    assert answer["offline_count"] == 3
    assert answer["stale_telemetry_count"] == 0
    assert answer["quiet_timestamp_count"] == 1
    assert "Roborock Q7 Max" in answer["message"]
    assert "Tuya Remote (bedroom 3)" in answer["message"]
    assert "Generic outlet" in answer["message"]
    assert "Live Hubitat healthStatus: offline" in answer["message"]


def test_health_scan_uses_detailed_all_device_states_not_healthcheck_filter():
    router = FakeLiveHealthRouter([], [])

    asyncio.run(router._device_health())

    assert len(router.calls) == 2
    stale_call = next(call for call in router.calls if call.get("filter"))
    live_call = next(call for call in router.calls if not call.get("filter"))
    assert stale_call["detailed"] is True
    assert stale_call["format"] == "detailed"
    assert "attributes" in stale_call["fields"]
    assert live_call["detailed"] is True
    assert live_call["format"] == "detailed"
    assert "currentStates" in live_call["fields"]
    assert "attributes" in live_call["fields"]
    assert "capabilityFilter" not in live_call
