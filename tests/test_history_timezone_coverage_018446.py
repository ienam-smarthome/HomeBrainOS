"""Generic history display and bounded page coverage; synthetic, read-only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from device_history_service import DeviceHistoryService
from history_temporal_analysis import history_temporal_evidence_details
from mcp_client import MCPToolResult

NOW = datetime(2026, 11, 6, 23, 50, tzinfo=timezone.utc)


def _row(dt, value, name="temperature"):
    return {
        "name": name, "value": str(value), "unit": "°C",
        "date": dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + dt.strftime("%z"),
        "isStateChange": True,
    }


class ReadOnlyPages:
    def __init__(self, events, *, zone="Europe/London", ignore_until=False):
        self.events = list(events)
        self.zone = zone
        self.ignore_until = ignore_until
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_get_info":
            return MCPToolResult(name, arguments, {}, "ok", {"timeZone": self.zone})
        assert name == "hub_read_devices"
        tool = arguments.get("tool")
        if tool == "hub_list_devices":
            return MCPToolResult(
                name, arguments, {}, "ok", {"devices": [{
                    "id": "5311", "label": "Example Sensor",
                    "capabilities": ["TemperatureMeasurement"],
                    "attributes": ["temperature"],
                }]},
            )
        assert tool == "hub_list_device_events"
        args = arguments["args"]
        assert args.get("deviceId") == "5311"
        assert "since" not in args
        rows = sorted(
            self.events, key=lambda e: e["date"], reverse=True
        )
        if args.get("until") and not self.ignore_until:
            from device_history_service import DeviceHistoryService
            end = DeviceHistoryService._event_datetime(args["until"])
            rows = [
                r for r in rows
                if DeviceHistoryService._event_datetime(r["date"]) <= end
            ]
        rows = rows[: args["limit"]]
        return MCPToolResult(name, arguments, {}, "ok", {"events": rows, "count": len(rows)})


def _service(mcp):
    return DeviceHistoryService(
        mcp, lambda *a, **kw: None, now=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_normal_planned_read_resolves_gmt_and_continues_capped_mixed_history():
    # Generic newest 50 cover only 50 minutes; several temperature events
    # are older than that despite lying within the user's 24h lookback.
    data = [
        _row(NOW - timedelta(minutes=i), 22, "battery")
        for i in range(129)
    ] + [
        _row(NOW - timedelta(minutes=1), 22.2),
        _row(NOW - timedelta(hours=2), 21.5),
        _row(NOW - timedelta(hours=18), 20.9),
        _row(NOW - timedelta(hours=24, minutes=5), 20.1, "battery"),
    ]
    mcp = ReadOnlyPages(data)
    result = await _service(mcp).history({
        "name": "Example Sensor",
        "attribute": "temperature",
        "hours_back": 24,
        "limit": 50,
        "_include_hub_time_zone": True,
        "_expand_history_coverage": True,
    })
    assert not result.is_error
    payload = result.data
    assert payload["timeZone"] == "Europe/London"
    assert payload["timeZoneSource"] == "hub_get_info"
    assert payload["sourceFirstPageAtLimit"] is True
    assert payload["sourcePagesFetched"] >= 3
    assert payload["sourceEventCount"] > 50
    assert payload["analysisEventCount"] == 3
    assert payload["sampleBounds"]["sampleCount"] == 3
    assert payload["sampleBounds"]["latestReturned"]["displayTime"] == (
        "2026-11-06 23:49:00 GMT"
    )
    assert payload["sampleBounds"]["earliestReturned"]["value"] == "20.9"
    assert payload["historySourceIntegrityVerified"] is False
    assert payload["sourceCoverageVerified"] is False
    assert sum(
        a.get("tool") == "hub_list_device_events"
        for _name, a in mcp.calls
    ) >= 3
    assert all(
        (a.get("tool") or "") == "hub_list_device_events"
        for name, a in mcp.calls
        if name == "hub_read_devices" and a.get("tool") != "hub_list_devices"
    )
    details = history_temporal_evidence_details(payload)
    assert details["timeZone"] == "Europe/London"
    assert details["sourcePagesFetched"] == payload["sourcePagesFetched"]
    assert details["sampleBounds"]["sampleCount"] == 3


@pytest.mark.asyncio
async def test_incomplete_retention_does_not_become_proof_of_24h_stability():
    events = [
        _row(NOW - timedelta(minutes=i), 22.2 if i % 17 == 0 else 90, (
            "temperature" if i % 17 == 0 else "battery"
        ))
        for i in range(75)
    ]
    result = await _service(ReadOnlyPages(events)).history({
        "name": "Example Sensor", "attribute": "temperature",
        "hours_back": 24, "limit": 50,
        "_expand_history_coverage": True,
    })
    data = result.data
    assert data["sourcePagesFetched"] == 2
    assert data["sourceCoverageStopReason"] == "older_source_page_short"
    assert data["sourceWindowBoundaryReached"] is False
    assert data["sourceCoverageVerified"] is False
    assert data["analysisEventCount"] > 3


@pytest.mark.asyncio
async def test_broken_until_bookmark_stops_without_repeated_unbounded_reads():
    events = [_row(NOW - timedelta(minutes=i), 20) for i in range(80)]
    mcp = ReadOnlyPages(events, ignore_until=True)
    result = await _service(mcp).history({
        "name": "Example Sensor", "attribute": "temperature",
        "hours_back": 24, "limit": 50,
        "_expand_history_coverage": True,
    })
    data = result.data
    assert data["sourcePagesFetched"] == 2
    assert data["sourceCoverageStopReason"] in {
        "source_ended_or_bookmark_not_honored",
        "duplicate_or_nonadvancing_page",
    }
    assert data["sourceWindowBoundaryReached"] is False
    assert data["sourceCoverageVerified"] is False
    assert len(mcp.calls) <= 4


@pytest.mark.asyncio
async def test_winter_gmt_and_summer_bst_use_verified_iana_zone_not_host_utc():
    cases = [
        ("2026-11-06T23:30:52.755+0000", "2026-11-06 23:30:52 GMT"),
        ("2026-07-01T23:30:52.755+0000", "2026-07-02 00:30:52 BST"),
    ]
    for timestamp, display in cases:
        event = {"name": "temperature", "value": "22.2",
                 "date": timestamp, "unit": "°C"}
        source = ReadOnlyPages([event])
        result = await _service(source).history({
            "name": "Example Sensor", "attribute": "temperature",
            "_include_hub_time_zone": True,
        })
        assert result.data["events"][0]["displayTime"] == display
        assert result.data["events"][0]["date"] == timestamp
        assert result.data["sampleBounds"]["latestReturned"]["displayTime"] == display


@pytest.mark.asyncio
async def test_no_authoritative_timezone_never_labels_utc_as_london_gmt():
    mcp = ReadOnlyPages([
        {"name": "temperature", "value": "22.2",
         "date": "2026-11-06T23:30:52.755+0000"}
    ], zone="Not/A_Zone")
    result = await _service(mcp).history({
        "name": "Example Sensor", "attribute": "temperature",
        "_include_hub_time_zone": True,
    })
    assert result.data["timeZone"] is None
    assert result.data["timeZoneSource"] == "runtime_fallback"
    assert "displayTime" not in result.data["events"][0]


def test_host_planner_hints_are_not_model_authored_or_public_receipt_arguments():
    orchestrator = (APP / "mcp_agent_orchestrator.py").read_text()
    executor = (APP / "tool_executor.py").read_text()
    for key in ("_include_hub_time_zone", "_expand_history_coverage"):
        assert f'args["{key}"] = True' in orchestrator
        assert f'receipt_arguments.pop("{key}", None)' in executor
