"""Windowed MCP event recovery: source-proven bounds, no invented history."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))

from causal_windowed_source import (
    build_focal_sensor_window_probe,
    verify_windowed_sensor_reply,
    merge_windowed_sensor_history,
)
from causal_history_coverage import assess_local_sensor_history_coverage


FOCAL = "2026-10-12T08:18:23.830+0100"
SPEC = {"name": "Room sensor", "attribute": "motion",
        "candidate": {"id": "123", "label": "Room sensor"}}
OLD = {"name": "motion", "value": "inactive",
       "date": "2026-10-12T08:18:23.761+0100"}
NEW = {"name": "motion", "value": "active",
       "date": "2026-10-12T08:19:11.046+0100"}


def request_and_reply(events=None):
    req = build_focal_sensor_window_probe(SPEC, FOCAL)
    result = {
        "deviceId": "123", "source": "device",
        "sinceMode": "explicit",
        "sinceTimestamp": req["since"],
        "untilTimestamp": req["until"],
        "events": events if events is not None else [OLD],
        "count": 1,
    }
    return req, result


def test_probe_is_narrow_and_absolute_not_recent_page():
    req, _ = request_and_reply()
    assert req == {
        "deviceId": "123", "attribute": "motion",
        "since": "2026-10-12T08:13:23.830+01:00",
        "until": "2026-10-12T08:20:23.830+01:00", "limit": 100,
    }
    assert build_focal_sensor_window_probe(
        {"candidate": {"id": "x"}, "attribute": "motion"}, FOCAL
    ) is None
    assert build_focal_sensor_window_probe(SPEC, "not-a-timestamp") is None


def test_focal_event_recovered_without_claiming_complete_history():
    req, response = request_and_reply()
    verified = verify_windowed_sensor_reply(req, response)
    assert verified["status"] == "verified-window"
    assert verified["events"] == [OLD]
    original = {
        "label": "Room sensor", "attribute": "motion",
        "events": [NEW], "observedEvents": [NEW],
    }
    before = assess_local_sensor_history_coverage([original], FOCAL)
    assert before["status"] == "pre-focal-not-observed-in-returned-pages"
    merged = merge_windowed_sensor_history(original, verified)
    assert len(merged["events"]) == 2
    assert len(merged["observedEvents"]) == 2
    assert merged["windowedEvidenceVerified"]
    after = assess_local_sensor_history_coverage([merged], FOCAL)
    assert after["status"] == "at-least-one-pre-focal-event-returned"
    assert not after["historicalCompletenessVerified"]


def test_older_server_ignoring_since_until_does_not_fabricate_evidence():
    req, response = request_and_reply()
    for key, val in [
        ("sinceMode", "relative"),
        ("untilTimestamp", None),
        ("sinceTimestamp", "2026-10-12T07:00:00+01:00"),
        ("deviceId", "999"),
    ]:
        r = dict(response)
        r[key] = val
        assert verify_windowed_sensor_reply(req, r)["events"] == []


def test_wrong_attribute_or_outside_window_excluded():
    req, response = request_and_reply([
        OLD, {"name": "temperature", "date": OLD["date"]},
        {"name": "motion", "date": "2026-10-12T08:01:00+0100"},
        {"name": "motion", "date": "unknown"},
    ])
    verified = verify_windowed_sensor_reply(req, response)
    assert verified["events"] == [OLD]


def test_empty_native_history_remains_unresolved_not_deleted():
    req, response = request_and_reply([])
    verified = verify_windowed_sensor_reply(req, response)
    assert verified["status"] == "verified-window"
    assert verified["events"] == []
    assert verified["sourceHistoryComplete"] is False
    assert verify_windowed_sensor_reply(req, {"success": False})["status"] == "unavailable"
    assert not merge_windowed_sensor_history(
        {"label": "Room sensor", "events": [NEW]},
        {"status": "unsupported-or-unverified-window", "events": [OLD]},
    ).get("windowedEvidenceVerified")


import pytest
from types import SimpleNamespace
from mcp_client import MCPToolResult
from mcp_agent_orchestrator import UnifiedMCPAgent
from request_metrics import RequestMetrics
import mcp_agent_orchestrator as host_module


class _MCP:
    def __init__(self, window_supported=True):
        self.window_supported = window_supported
        self.calls = []

    def peek_device_identities(self):
        return [
            {"id": "100", "label": "Example Light", "room": "Example", "capabilities": ["Switch"], "attributes": {"switch": "off"}},
            {"id": "123", "label": "Room sensor", "room": "Example", "capabilities": ["MotionSensor"], "attributes": {"motion": "active"}},
            {"id": "124", "label": "Second sensor", "room": "Example", "capabilities": ["MotionSensor"], "attributes": {"motion": "active"}},
        ]

    async def call_tool(self, name, request):
        self.calls.append(request)
        args = request["args"]
        data = {
            "deviceId": args["deviceId"],
            "events": [OLD] if args["deviceId"] == "123" else [],
        }
        if self.window_supported:
            data.update({
                "sinceMode": "explicit", "sinceTimestamp": args["since"],
                "untilTimestamp": args["until"],
            })
        return MCPToolResult(name, request, {}, "ok", data)


class _Executor:
    def __init__(self):
        self.calls = []

    async def execute(self, name, arguments, **kwargs):
        self.calls.append(arguments)
        subject = arguments.get("name")
        data = {
            "label": subject,
            "room": "Example", "attribute": arguments.get("attribute"),
            "events": [NEW], "observedEvents": [NEW],
        }
        if subject == "Example Light":
            data["events"] = []
            data["observedEvents"] = []
        return SimpleNamespace(
            success=True, result=MCPToolResult(name, arguments, {}, "ok", data)
        )


class _Evidence:
    def __init__(self):
        self.records = []

    def record(self, tool, args, **kwargs):
        self.records.append({"tool": tool, "arguments": args, **kwargs})


class _Catalogue:
    def declared_tool(self, name):
        return object()

    def available_tool(self, name):
        return object()


@pytest.mark.asyncio
@pytest.mark.parametrize("supports_window", [True, False])
async def test_orchestrator_recovers_only_local_window_and_stops_cross_room(
    monkeypatch, supports_window,
):
    sensors = [
        {"name": label, "attribute": "motion", "candidate": {"id": id_, "label": label, "room": "Example"}}
        for id_, label in [("123", "Room sensor"), ("124", "Second sensor")]
    ]
    monkeypatch.setattr(
        host_module.DeviceQueryService, "cached_room_event_source_hints",
        staticmethod(lambda *args, **kwargs: [{"name": "Room sensor"}]),
    )
    monkeypatch.setattr(host_module, "controller_history_candidates", lambda *a, **k: [])
    monkeypatch.setattr(host_module, "trigger_sensor_history_candidates", lambda *a, **k: sensors)
    monkeypatch.setattr(
        host_module, "prioritize_known_automation_sensor_candidates",
        lambda pool, *a, **k: (pool[:2], False),
    )
    mcp = _MCP(window_supported=supports_window)
    recorder = _Evidence()
    host = SimpleNamespace(
        mcp=mcp, evidence=recorder, executor=_Executor(),
        known_automations=[], _tool_succeeded=lambda result: not result.is_error,
    )
    history = {
        "label": "Example Light", "deviceId": "100", "room": "Example",
        "correlationEvents": [
            {"name": "switch", "value": "on", "date": "2026-10-12T08:16:10.861+0100"},
            {"name": "switch", "value": "off", "date": FOCAL},
        ],
    }
    metric = RequestMetrics()
    token = metric.begin()
    try:
        await UnifiedMCPAgent._collect_reporting_source_secondary_correlation(
            host,
            subject_history=history, transition="off",
            boundary_match={"stateBoundary": FOCAL},
            catalog=_Catalogue(), completed_calls=set(),
        )
        counters = metric.snapshot()["counters"]
    finally:
        metric.reset(token)
    analysis = next(row["details"] for row in recorder.records
        if row["tool"] == "homebrain_causal_secondary_correlation")
    assert len(mcp.calls) == 2, mcp.calls
    assert all(call["tool"] == "hub_list_device_events" for call in mcp.calls)
    assert all("since" in call["args"] and "until" in call["args"] for call in mcp.calls)
    assert analysis["discoveryCoverage"]["outsideRoomAttempted"] == 0
    assert counters.get("causal_focal_window_reads") == 2
    if supports_window:
        assert analysis["localSensorHistoryCoverage"]["preFocalObserved"] is True
        assert analysis["discoveryCoverage"]["crossRoomSkippedForLocalOffEvidence"]
        assert any(r["eventValue"] == "inactive" for sensor in analysis["sensors"]
                   for r in sensor.get("relevantCorrelations") or [])
    else:
        assert not analysis["localSensorHistoryCoverage"]["preFocalObserved"]
        assert analysis["discoveryCoverage"]["crossRoomSkippedForFocalHistoryGap"]
        assert all(s["status"] == "unsupported-or-unverified-window"
                   for s in analysis["focalWindowRetrieval"])
