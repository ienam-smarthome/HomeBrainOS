from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_light_usage import FastFallbackRouter, is_light_usage_today_query  # noqa: E402
from light_usage_calculation import calculate_on_time, switch_events  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from routing_policy import classify_query  # noqa: E402


def result(name: str, data: Any, *, error: bool = False, text: str = "") -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw={"isError": error},
        text=text,
        data=data,
        is_error=error,
    )


def test_light_usage_query_routes_to_deterministic_mcp_fast_path():
    assert is_light_usage_today_query("total lights on time today") is True
    assert is_light_usage_today_query("How long have the lights been on today?") is True
    decision = classify_query("total lights on time today")
    assert decision.route == "mcp-fast"
    assert "historical event calculation" in decision.reason


def test_midnight_spanning_interval_is_clipped_to_today():
    timezone = datetime.now().astimezone().tzinfo
    start = datetime(2026, 7, 19, 0, 0, tzinfo=timezone)
    now = datetime(2026, 7, 19, 18, 20, tzinfo=timezone)
    events = [
        (start - timedelta(minutes=30), "on"),
        (start + timedelta(hours=2, minutes=30), "off"),
    ]

    calculated = calculate_on_time(events, start, now, "off")

    assert calculated["seconds"] == 2.5 * 3600
    assert calculated["state_known_at_start"] is True
    assert calculated["incomplete"] is False


def test_unmatched_off_event_is_flagged_but_not_assumed_from_midnight():
    timezone = datetime.now().astimezone().tzinfo
    start = datetime(2026, 7, 19, 0, 0, tzinfo=timezone)
    now = datetime(2026, 7, 19, 18, 20, tzinfo=timezone)
    events = [(start + timedelta(hours=9, minutes=32), "off")]

    calculated = calculate_on_time(events, start, now, "off")

    assert calculated["seconds"] == 0
    assert calculated["incomplete"] is True
    assert calculated["unmatched_off_times"]
    assert "midnight state unknown" in calculated["notes"]


def test_event_parser_accepts_hubitat_iso_switch_rows():
    timezone = datetime.now().astimezone().tzinfo
    payload = {
        "events": [
            {"name": "switch", "value": "on", "date": "2026-07-19T01:00:00+01:00"},
            {"name": "switch", "value": "off", "date": "2026-07-19T02:00:00+01:00"},
            {"name": "power", "value": "24", "date": "2026-07-19T01:30:00+01:00"},
        ]
    }

    parsed = switch_events(payload, timezone)

    assert [state for _, state in parsed] == ["on", "off"]


class UsageClient:
    def __init__(self, *, fail_events: bool = False) -> None:
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_events = fail_events
        self.devices = [
            {
                "id": "1",
                "label": "My Floor Lamp",
                "room": "Bedroom 1",
                "currentStates": {"switch": "off"},
            },
            {
                "id": "2",
                "label": "Bedroom 3 Light",
                "room": "Bedroom 3",
                "currentStates": {"switch": "off"},
            },
            {
                "id": "3",
                "label": "Bedroom PC socket",
                "room": "Sockets",
                "currentStates": {"switch": "on"},
            },
        ]
        self.events = {
            "1": [
                {"name": "switch", "value": "on", "date": (start - timedelta(minutes=30)).isoformat()},
                {"name": "switch", "value": "off", "date": (start + timedelta(hours=2, minutes=30)).isoformat()},
            ],
            "2": [
                {"name": "switch", "value": "on", "date": (start + timedelta(hours=3)).isoformat()},
                {"name": "switch", "value": "off", "date": (start + timedelta(hours=4)).isoformat()},
            ],
        }

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        if name == "hub_list_devices":
            return result(name, {"devices": self.devices})
        if name == "hub_list_device_events":
            if self.fail_events:
                return result(name, None, error=True, text="event history disabled")
            device_id = str(args.get("deviceId"))
            return result(name, {"events": self.events.get(device_id, [])})
        raise AssertionError((name, args))


class DirectUsageRouter(FastFallbackRouter):
    async def _live_devices(self, capability_filter: str | None = None):
        return await self.client.call_tool(
            "hub_list_devices",
            {"capabilityFilter": capability_filter},
        )


def test_router_adds_individual_light_durations_as_bulb_hours():
    client = UsageClient()
    router = DirectUsageRouter(client)

    answer = asyncio.run(router.answer("total lights on time today"))

    assert answer["success"] is True
    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "fallback-light-usage-today"
    assert answer["combined_seconds"] == 3.5 * 3600
    assert answer["lights_with_usage"] == 2
    assert "bulb-hours" in answer["message"]
    assert "not wall-clock elapsed time" in answer["message"]
    event_calls = [args for name, args in client.calls if name == "hub_list_device_events"]
    assert {str(item["deviceId"]) for item in event_calls} == {"1", "2"}
    assert all(item["hoursBack"] == 36 for item in event_calls)


def test_event_failure_is_transparent_and_never_delegated_to_cloud():
    client = UsageClient(fail_events=True)
    router = DirectUsageRouter(client)

    answer = asyncio.run(router.answer("total lights on time today"))

    assert answer["success"] is False
    assert answer["route"] == "mcp-fast"
    assert answer["intent"] == "fallback-light-usage-today-unavailable"
    assert '"cloud_fallback_blocked": true' in answer["technical"]
    assert answer["display"]["metrics"][2]["value"] == "Not used"
