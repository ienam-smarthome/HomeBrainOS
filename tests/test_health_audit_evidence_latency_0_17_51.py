"""0.17.51: observe actual MCP page latency and conflicting device-health clocks.

No extra Hubitat reads and no change to device health verdicts. These are
in-memory simulations of already-approved projected MCP pages.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from health_audit_service import (
    _device_findings, render_comprehensive_system_audit,
)
from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult


CHECKED = datetime(2026, 10, 13, 23, 21, 22, tzinfo=timezone.utc)


def offline_device(seconds_old: int, *, device_id="3483"):
    stamp = (CHECKED - timedelta(seconds=seconds_old)).isoformat()
    return {
        "id": device_id, "label": "Tuya Remote (bedroom 3)",
        "attributes": {
            "healthStatus": "offline",
            "lastActivity": stamp,
        },
    }


def test_recent_activity_conflict_is_reported_without_suppressing_offline_issue():
    device = offline_device(10)
    section, issues = _device_findings([device], low_battery_threshold=20, now=CHECKED)
    assert section["offline_count"] == 1
    row = section["offline"][0]
    assert row["source_attribute"] == "healthStatus"
    assert row["recent_activity_conflict"] is True
    assert row["last_activity_age_seconds"] == 10
    assert row["reachability_independently_verified"] is False
    assert row["recent_activity_does_not_verify_online"] is True
    assert [item["category"] for item in issues] == ["device-offline"]


def test_old_or_future_activity_does_not_falsely_assert_conflict():
    devices = [
        offline_device(3600, device_id="3483"),
        offline_device(-120, device_id="3484"),
    ]
    section, issues = _device_findings(devices, low_battery_threshold=20, now=CHECKED)
    assert len(issues) == 2
    assert all(not row["recent_activity_conflict"] for row in section["offline"])


def test_audit_reports_conflict_as_unverified_not_automatic_online():
    section, issues = _device_findings(
        [offline_device(10)], low_battery_threshold=20, now=CHECKED,
    )
    snapshot = {
        "checked_at": CHECKED.isoformat(),
        "status": "attention", "attention_count": 1,
        "issues": issues,
        "sections": {
            "devices": section,
            "automations": {"total": 0, "attention_count": 0},
            "logs": {"entries_checked": 0, "checked_hours": 24},
        },
        "stage_timings_ms": {"device_inventory": 21000},
    }
    section["read_provenance"] = {
        "source": "fresh_projected_gateway", "mode": "bounded_parallel_pages",
        "complete": True, "pages": 5,
        "page_timings_ms": [
            {"offset": 0, "elapsed_ms": 4512, "success": True},
            {"offset": 50, "elapsed_ms": 10111, "success": True},
            {"offset": 100, "elapsed_ms": 9000, "success": True},
            {"offset": 150, "elapsed_ms": 12000, "success": True},
            {"offset": 200, "elapsed_ms": 3500, "success": True},
        ],
        "parallel_page_max_concurrent": 2,
    }
    text = render_comprehensive_system_audit(snapshot, None)
    assert "Status/activity conflict" in text
    assert "10 seconds" in text
    assert "stale health flag" in text
    assert "fresh projection verified=True" in text
    assert "offset=milliseconds" in text
    assert "50=10111ms" in text
    assert "bounded concurrency=2" in text
    assert "not measured Hubitat CPU usage" in text


@pytest.mark.asyncio
async def test_verified_parallel_audit_page_latencies_are_measured_without_more_calls():
    client = HubitatMCPClient("http://127.0.0.1:1/mcp", max_concurrent_calls=2)
    requests = []

    async def list_tools(refresh=False):
        return [MCPTool("hub_read_devices", "", {"type": "object"})]

    async def call_tool(name, arguments):
        assert name == "hub_read_devices"
        args = arguments["args"]
        offset = args["offset"]
        requests.append(offset)
        assert args["limit"] == 50
        assert "commands" not in args["fields"]
        assert "attributes" in args["fields"]
        count = 50 if offset == 0 else 1
        items = [
            {"id": str(offset+i+1), "label": f"Device {offset+i+1}",
             "attributes": {}, "capabilities": []}
            for i in range(count)
        ]
        return MCPToolResult(
            name=name, arguments=arguments, raw={},
            text="", data={
                "devices": items, "total": 51,
                "hasMore": offset == 0,
                "nextOffset": 50 if offset == 0 else None,
            },
        )

    async def fallback(*args, **kwargs):
        raise AssertionError("Complete projected pages must not request fallback")

    client.list_tools = list_tools
    client.call_tool = call_tool
    client.get_cached_devices = fallback
    try:
        devices, provenance = await client.get_audit_devices()
    finally:
        await client.close()
    assert len(devices) == 51
    assert requests == [0, 50]
    assert provenance["source"] == "fresh_projected_gateway"
    assert provenance["mode"] == "bounded_parallel_pages"
    assert provenance["complete"] is True
    assert provenance["pages"] == 2
    assert provenance["page_timings_are_end_to_end_mcp_not_hub_cpu"] is True
    assert provenance["parallel_page_max_concurrent"] == 2
    assert [row["offset"] for row in provenance["page_timings_ms"]] == [0, 50]
    assert all(row["elapsed_ms"] >= 0 and row["success"]
               for row in provenance["page_timings_ms"])
    assert provenance["slowest_page_ms"] >= provenance["first_page_ms"]


@pytest.mark.asyncio
async def test_failed_projected_page_remains_unverified_and_records_timing():
    client = HubitatMCPClient("http://127.0.0.1:1/mcp", max_concurrent_calls=2)

    async def list_tools(refresh=False):
        return [MCPTool("hub_read_devices", "", {"type": "object"})]

    async def call_tool(name, arguments):
        raise RuntimeError("backend slow response")

    async def fallback(*args, **kwargs):
        return [{"id": "1", "label": "Fallback", "attributes": {}}]

    client.list_tools = list_tools
    client.call_tool = call_tool
    client.get_cached_devices = fallback
    try:
        devices, provenance = await client.get_audit_devices()
    finally:
        await client.close()
    assert len(devices) == 1
    assert provenance["source"] == "full_detailed_fallback"
    assert provenance["complete"] is False
    assert provenance["page_timings_ms"][0]["success"] is False
    assert provenance["read_elapsed_ms"] >= 0
