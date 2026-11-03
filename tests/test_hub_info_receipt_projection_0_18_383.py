"""Q1 allowlisted Hub Info source evidence: no raw household fields.

Synthetic data only. The public evidence receipt contains measured scalar facts
for independent review, not a complete device record or a health conclusion.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from hub_info_receipt_projection import hub_info_receipt_details
from evidence_recorder import EvidenceRecorder
from mcp_client import MCPTool, MCPToolResult
from tool_executor import ToolExecutor
from tool_registry import ToolEffect, LOCAL_HUB_INFO_TOOL


def snapshot(scope="full"):
    return {
        "success": True,
        "scope": scope,
        "source": "PRIVATE-HUB-DEVICE-NAME",
        "ip_address": "10.1.2.3",
        "device_id": "PRIVATE-DEVICE-ID",
        "installed_firmware": "2.5.3.117",
        "update_status": "up to date",
        "available_firmware": "2.5.3.117",
        "update_available": False,
        "cpu_5_min": "0.67",
        "cpu_percent": "16.75",
        "free_memory": 941.71,
        "free_memory_unit": "MB",
        "temperature": 45.9,
        "temperature_unit": "°C",
        "uptime": "0d:0h:26m:48s",
        "database_size": "203",
        "database_size_unit": "MB",
        "zigbee_status": "online",
        "zwave_status": "disabled",
        "matter_status": "online",
        "hub_alerts": "PRIVATE-ALERT-DEVICE-LABEL",
        "poll_read_count": 4,
        "poll_sleep_ms": 1500,
        "refresh_command_count": 2,
        "firmware_status_settled": True,
        "custom_password": "SECRET-PRIVATE-TOKEN",
    }


def test_source_value_projection_reproduces_supported_facts_without_private_fields():
    details = hub_info_receipt_details({"scope": "full"}, snapshot())
    assert details["sourceType"] == "hub_information_driver"
    assert details["sourceScopeMatched"] is True
    fields = details["reported"]
    assert fields["cpu_5_min"] == pytest.approx(0.67)
    assert fields["cpu_percent"] == pytest.approx(16.75)
    assert fields["free_memory"] == pytest.approx(941.71)
    assert fields["temperature"] == pytest.approx(45.9)
    assert fields["database_size"] == pytest.approx(203)
    assert fields["installed_firmware"] == "2.5.3.117"
    assert fields["zwave_status"] == "disabled"
    assert fields["uptime"] == "0d:0h:26m:48s"
    assert fields["temperature_unit"] == "°C"
    assert "hub_alerts" not in fields  # free-text alert is not proof of absence
    assert "update_available" not in fields  # derived default is not raw status
    assert details["snapshotDiagnostics"] == {
        "poll_read_count": 4, "poll_sleep_ms": 1500,
        "refresh_command_count": 2, "firmware_status_settled": True,
    }
    assert "PRIVATE" not in str(details)
    assert "10.1.2.3" not in str(details)
    assert "SECRET" not in str(details)


@pytest.mark.parametrize("scope", ["resources", "firmware", "full"])
def test_projector_accepts_all_named_scopes_but_not_unsourced_scope(scope):
    snap = snapshot(scope)
    assert hub_info_receipt_details({"scope": scope}, snap)["requestedScope"] == scope
    assert hub_info_receipt_details({"scope": "other"}, snap) is None
    assert hub_info_receipt_details({"scope": "full"}, {"success": False, **{"scope": "full"}}) is None
    wrong = dict(snap, scope="firmware" if scope != "firmware" else "resources")
    assert hub_info_receipt_details({"scope": scope}, wrong) is None


def test_unknown_value_formats_do_not_prove_status_or_leak_raw_text():
    snap = snapshot()
    snap.update({
        "cpu_percent": "100%; 10.1.2.3",
        "temperature": "NaN",
        "free_memory": 10 ** 200,
        "installed_firmware": "192.168.1.239",
        "zigbee_status": "PRIVATE-USER-NAME",
        "update_status": "PRIVATE-SECRET-TEXT",
        "hub_alerts": "PRIVATE-BROKEN-DEVICE-LABEL",
        "uptime": "28 seconds since reboot",
        "poll_read_count": True,
        "poll_sleep_ms": -10,
        "refresh_command_count": "2",
    })
    details = hub_info_receipt_details({"scope": "full"}, snap)
    fields = details["reported"]
    for name in ["cpu_percent", "temperature", "free_memory",
                 "installed_firmware", "zigbee_status", "update_status",
                 "hub_alerts", "uptime"]:
        assert name not in fields
    assert details["snapshotDiagnostics"] == {"firmware_status_settled": True}
    assert "PRIVATE" not in str(details)


def test_driver_alert_absence_is_only_reported_for_strict_source_token():
    for value in ("none", "no alerts", "0", 0):
        snap = snapshot()
        snap["hub_alerts"] = value
        details = hub_info_receipt_details({"scope": "full"}, snap)
        assert details["reported"]["hub_alerts"] == value


class NoRemote:
    async def call_tool(self, *_args, **_kwargs):
        raise AssertionError("No remote call was permitted")


@pytest.mark.asyncio
async def test_local_snapshot_records_value_receipt_without_changing_answer_or_tools():
    data = snapshot()
    async def local(arguments):
        assert arguments == {"scope": "full"}
        return MCPToolResult(LOCAL_HUB_INFO_TOOL, arguments, {}, "", data)

    evidence = EvidenceRecorder()
    executor = ToolExecutor(
        NoRemote(), evidence, local_handlers={LOCAL_HUB_INFO_TOOL: local}
    )
    token = evidence.begin()
    try:
        result = await executor.execute(
            LOCAL_HUB_INFO_TOOL, {"scope": "full"},
            tool=MCPTool(LOCAL_HUB_INFO_TOOL, "Hub Information snapshot", {},
                         annotations={"effect": ToolEffect.READ.value}),
            evidence_kind="authoritative_hub_info_snapshot",
        )
        receipts = evidence.receipts()
    finally:
        evidence.reset(token)

    assert result.success is True
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["evidence_kind"] == "authoritative_hub_info_snapshot"
    assert receipt["mutates"] is False
    assert receipt["effect"] == "read"
    assert receipt["details"]["reported"]["cpu_percent"] == pytest.approx(16.75)
    assert "SECRET" not in str(receipt)
    assert "PRIVATE" not in str(receipt)
    assert "ip_address" not in str(receipt)
