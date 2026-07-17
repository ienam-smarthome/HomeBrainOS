from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_prayer_times import FastFallbackRouter, extract_prayer_times  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from mcp_state_broker import MCPStateBroker  # noqa: E402
from routing_policy import classify_query  # noqa: E402


PRAYER_HTML = """
<div class="prayer-times">
  🌙 Fajr 03:11<br>
  🌅 Sunrise 05:00<br>
  ☀️ Dhuhr 13:12<br>
  ☁️ Asr 18:36<br>
  🌆 Maghrib 21:12<br>
  🌌 Isha 22:19
</div>
"""


class FakePrayerClient:
    def __init__(self, *, current_html: bool = True) -> None:
        self.current_html = current_html
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.server_info = {"name": "Hubitat MCP", "version": "3.4.1"}
        self.configured = True
        self.tools = [
            MCPTool(
                "hub_read_devices",
                "Read-only gateway: hub_list_devices, hub_list_device_events",
                {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "args": {"type": "object"},
                    },
                },
            )
        ]

    async def initialize(self, force: bool = False) -> None:
        return None

    async def close(self) -> None:
        return None

    async def list_tools(self, refresh: bool = False):
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        self.calls.append((name, arguments))
        hidden = arguments.get("tool") if name == "hub_read_devices" else name
        args = arguments.get("args", {}) if name == "hub_read_devices" else arguments

        if hidden == "hub_list_devices":
            states = {"html": PRAYER_HTML} if self.current_html else {"status": "available"}
            data = {
                "devices": [
                    {
                        "id": "101",
                        "label": "Pray times",
                        "room": "Apps",
                        "lastActivity": "2026-07-17T17:05:00+01:00",
                        "currentStates": states,
                    }
                ]
            }
        elif hidden == "hub_list_device_events":
            assert args["deviceId"] == "101"
            data = {
                "events": [
                    {
                        "name": "html",
                        "value": PRAYER_HTML,
                        "date": "2026-07-17T17:05:00+01:00",
                    }
                ]
            }
        else:
            raise AssertionError(f"Unexpected tool call: {hidden}")

        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data=data,
            is_error=False,
        )


def test_extract_prayer_times_from_html():
    assert extract_prayer_times(PRAYER_HTML) == {
        "Fajr": "03:11",
        "Sunrise": "05:00",
        "Dhuhr": "13:12",
        "Asr": "18:36",
        "Maghrib": "21:12",
        "Isha": "22:19",
    }


def test_prayer_time_queries_route_to_mcp_fast():
    for query in (
        "What time is Fajr?",
        "When is Maghrib?",
        "Isha time",
        "Show prayer times",
        "What are today's prayer times?",
    ):
        assert classify_query(query).route == "mcp-fast"


def test_single_prayer_time_uses_current_state_without_events():
    fake = FakePrayerClient(current_html=True)
    router = FastFallbackRouter(MCPStateBroker(fake), cpu_probe_enabled=False)

    answer = asyncio.run(router.answer("What time is Fajr?"))

    assert answer["success"] is True
    assert answer["intent"] == "fallback-prayer-times"
    assert answer["message"] == "Fajr is at 03:11 today."
    assert answer["requested_prayer"] == "Fajr"
    assert answer["display"]["metrics"][0]["value"] == "03:11"
    assert not any(
        call[1].get("tool") == "hub_list_device_events" for call in fake.calls
    )


def test_all_prayer_times_fall_back_to_latest_event_and_clean_html():
    fake = FakePrayerClient(current_html=False)
    router = FastFallbackRouter(MCPStateBroker(fake), cpu_probe_enabled=False)

    answer = asyncio.run(router.answer("Show prayer times"))

    assert answer["success"] is True
    assert answer["intent"] == "fallback-prayer-times"
    assert answer["prayer_times"]["Dhuhr"] == "13:12"
    assert answer["prayer_times"]["Isha"] == "22:19"
    assert "<div" not in answer["message"]
    assert len(answer["display"]["items"]) == 6
    assert any(
        call[1].get("tool") == "hub_list_device_events" for call in fake.calls
    )


def test_prayer_times_events_are_presented_as_times_not_raw_html():
    fake = FakePrayerClient(current_html=False)
    router = FastFallbackRouter(MCPStateBroker(fake), cpu_probe_enabled=False)

    answer = asyncio.run(router.answer("Show prayer times events"))

    assert answer["success"] is True
    assert answer["intent"] == "fallback-prayer-times"
    assert answer["display"]["title"] == "Prayer times"
    assert answer["display"]["metrics"][0]["label"] == "Fajr"
    assert answer["display"]["metrics"][0]["value"] == "03:11"
    assert "html" not in answer["message"].lower()


def test_backup_is_not_misclassified_as_routine_read_only():
    decision = classify_query("do a hub backup")
    assert decision.route == "ollama-planner"
