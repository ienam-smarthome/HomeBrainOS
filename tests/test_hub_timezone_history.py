from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from history_time_windows import (  # noqa: E402
    parse_history_window_request,
    reset_history_window_request,
    resolve_history_window,
    set_history_window_request,
)
from hub_timezone import (  # noqa: E402
    HubTimezoneResolver,
    required_history_hours_absolute,
)
from mcp_client import MCPToolResult  # noqa: E402


UTC_NOW = datetime(2026, 9, 17, 19, 37, tzinfo=timezone.utc)


def _event(value: str, timestamp: str) -> dict:
    return {
        "name": "switch",
        "value": value,
        "date": timestamp,
        "isStateChange": True,
    }


EVENTS = [
    _event("off", "2026-09-17T07:34:00.000+0100"),
    _event("on", "2026-09-17T04:56:00.000+0100"),
    _event("off", "2026-09-17T04:00:00.000+0100"),
    _event("on", "2026-09-17T03:49:00.000+0100"),
    _event("off", "2026-09-17T03:27:00.000+0100"),
    _event("on", "2026-09-17T03:00:00.100+0100"),
    _event("off", "2026-09-17T03:00:00.000+0100"),
    _event("on", "2026-09-17T02:37:00.000+0100"),
    _event("off", "2026-09-17T02:00:00.000+0100"),
    _event("on", "2026-09-17T01:08:00.000+0100"),
    _event("off", "2026-09-16T17:00:00.000+0100"),
]


class HubTimezoneMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_get_info":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "timeZone": "Europe/London",
                    # Other hub_get_info PII must never be copied into evidence.
                    "localIP": "192.0.2.10",
                    "latitude": 51.5,
                    "longitude": -0.1,
                },
            )
        operation = arguments.get("tool")
        if operation == "hub_list_devices":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "devices": [{
                        "id": "7827",
                        "label": "Big lamp",
                        "capabilities": ["Switch"],
                        "commands": ["on", "off"],
                    }]
                },
            )
        if operation == "hub_list_device_events":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {"events": EVENTS},
            )
        raise AssertionError((name, arguments))


def _event_call(mcp: HubTimezoneMCP) -> dict:
    return next(
        arguments
        for _name, arguments in reversed(mcp.calls)
        if arguments.get("tool") == "hub_list_device_events"
    )


@pytest.mark.asyncio
async def test_semantic_history_uses_hub_timezone_not_utc_container() -> None:
    evidence: list[tuple[tuple, dict]] = []
    mcp = HubTimezoneMCP()
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: evidence.append((args, kwargs)),
        now=lambda: UTC_NOW,
    )
    token = set_history_window_request(
        parse_history_window_request("How long was big lamp on last night?")
    )
    try:
        result = await service.history({
            "name": "big lamp",
            "attribute": "switch",
            "hours_back": 24,
        })
    finally:
        reset_history_window_request(token)

    assert result.is_error is False
    assert isinstance(result.data, dict)
    window = result.data["timeWindow"]
    assert window["start"] == "2026-09-16T18:00:00+01:00"
    assert window["end"] == "2026-09-17T08:00:00+01:00"
    assert window["timeZone"] == "Europe/London"
    assert window["timeZoneSource"] == "hub_get_info"
    assert window["startUtcOffset"] == "+01:00"
    assert window["endUtcOffset"] == "+01:00"
    assert _event_call(mcp)["args"]["hoursBack"] == 28
    assert result.data["hoursBack"] == 28

    timezone_receipts = [
        kwargs
        for args, kwargs in evidence
        if args and args[0] == "hub_get_info"
    ]
    assert len(timezone_receipts) == 1
    assert timezone_receipts[0]["summary"] == "Hub timezone Europe/London"
    assert "192.0.2.10" not in str(timezone_receipts[0])
    assert "51.5" not in str(timezone_receipts[0])


@pytest.mark.asyncio
async def test_hub_timezone_is_cached_for_repeated_semantic_history_reads() -> None:
    mcp = HubTimezoneMCP()
    service = DeviceHistoryService(
        mcp,
        lambda *args, **kwargs: None,
        now=lambda: UTC_NOW,
    )
    parsed = parse_history_window_request("How long was big lamp on last night?")
    for _ in range(2):
        token = set_history_window_request(parsed)
        try:
            result = await service.history({"name": "big lamp", "attribute": "switch"})
            assert result.is_error is False
        finally:
            reset_history_window_request(token)

    assert sum(1 for name, _arguments in mcp.calls if name == "hub_get_info") == 1
    assert result.data["timeWindow"]["timeZoneSource"] == "hub_get_info_cache"


def test_absolute_history_fetch_buffer_is_dst_safe_on_london_fallback() -> None:
    london = ZoneInfo("Europe/London")
    now = datetime(2026, 10, 25, 9, 0, tzinfo=london)
    request = parse_history_window_request("How long was the lamp on last night?")
    window = resolve_history_window(request, now=now)

    assert window is not None
    assert window.start.isoformat() == "2026-10-24T18:00:00+01:00"
    assert window.end.isoformat() == "2026-10-25T08:00:00+00:00"
    # 18:00 BST is 17:00 UTC; 09:00 GMT is 09:00 UTC the next day: 16h age,
    # plus one hour of predecessor-state buffer => 17 hoursBack.
    assert required_history_hours_absolute(window.start, now=now) == 17


@pytest.mark.asyncio
async def test_resolver_rejects_invalid_hub_timezone_and_keeps_aware_runtime_clock() -> None:
    class InvalidTimezoneMCP:
        async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
            assert name == "hub_get_info"
            return MCPToolResult(name, arguments, {}, "ok", {"timeZone": "Not/A_Zone"})

    runtime = datetime(2026, 9, 17, 20, 0, tzinfo=ZoneInfo("Europe/Paris"))
    resolver = HubTimezoneResolver(
        InvalidTimezoneMCP(),
        lambda *args, **kwargs: None,
    )
    resolved, name, source = await resolver.now_in_hub_timezone(lambda: runtime)

    assert resolved is runtime
    assert name == "Europe/Paris"
    assert source == "runtime_fallback"
