"""Generic current-device lookup proof, sourced from the native wire contract.

All device names and values here are synthetic. No real hub or model is called.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from device_query_service import DeviceQueryService
from evidence_recorder import EvidenceRecorder
from mcp_client import MCPTool, MCPToolResult, HubitatMCPClient
from request_metrics import RequestMetrics
from tool_executor import ToolExecutor
from tool_registry import ToolEffect


def fake_result(data: dict, *, error=False) -> MCPToolResult:
    return MCPToolResult("hub_read_devices", {}, {}, "", data, is_error=error)


class FakeGateway:
    def __init__(self, data: dict, *, error=False):
        self.calls = []
        self.result = fake_result(data, error=error)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result

    def peek_device_identities(self):
        return []

    async def get_device_identities(self):
        return []


@pytest.mark.asyncio
async def test_rejected_targeted_read_is_unresolved_and_not_device_absence():
    mcp = FakeGateway({
        "success": False,
        "error": "Unknown argument: detailed",
    }, error=True)
    metrics, receipts = RequestMetrics(), []
    token = metrics.begin()
    try:
        service = DeviceQueryService(
            mcp, lambda *args, **kw: receipts.append((args, kw))
        )
        result = await service.resolve_device({"name": "Synthetic Lamp"})
        outcome = metrics.completed_outcome()
        snapshot = metrics.finish(outcome)
    finally:
        metrics.reset(token)

    assert result.is_error
    assert len(mcp.calls) == 1
    assert mcp.calls[0][1]["tool"] == "hub_list_devices"
    assert len(receipts) == 1
    assert receipts[0][1]["success"] is False
    assert receipts[0][1]["supports_live_claim"] is False
    assert "device_resolution_source_failed" in snapshot["counters"]
    assert snapshot["outcome"] == "unresolved"
    assert "Synthetic Lamp" not in json.dumps(result.data.get("target"))


@pytest.mark.asyncio
async def test_source_complete_targeted_read_can_resolve_exact_device_and_states():
    mcp = FakeGateway({
        "success": True,
        "devices": [{
            "id": "801",
            "label": "Synthetic Lamp",
            "room": "Study",
            "capabilities": ["Switch", "SwitchLevel"],
            "attributes": [
                {"name": "switch", "currentValue": "on"},
                {"name": "level", "currentValue": 60},
            ],
            "commands": ["on", "off", "setLevel"],
        }],
        "count": 1,
        "total": 1,
    })
    metrics, receipts = RequestMetrics(), []
    token = metrics.begin()
    try:
        result = await DeviceQueryService(
            mcp, lambda *args, **kw: receipts.append((args, kw))
        ).resolve_device({"name": "Synthetic Lamp"})
        outcome = metrics.completed_outcome()
        snapshot = metrics.finish(outcome)
    finally:
        metrics.reset(token)

    assert result.is_error is False
    assert result.data["matched"] is True
    assert str(result.data["deviceId"]) == "801"
    assert len(mcp.calls) == 1
    assert result.data["target"]["attributes"][1]["currentValue"] == 60
    assert receipts[0][1]["success"] is True
    assert snapshot["outcome"] == "success"
    assert "device_resolution_source_failed" not in snapshot["counters"]


@pytest.mark.asyncio
async def test_failed_local_resolver_receipt_does_not_support_live_claim():
    async def failed_resolver(arguments):
        return MCPToolResult(
            "homebrain_resolve_device", arguments, {}, "",
            {"error": "Read rejected"}, is_error=True,
        )

    class MustNotCall:
        async def call_tool(self, *_args, **_kw):
            raise AssertionError("Remote command was not requested")

    evidence = EvidenceRecorder()
    recorder = ToolExecutor(
        MustNotCall(), evidence,
        local_handlers={"homebrain_resolve_device": failed_resolver},
    )
    token = evidence.begin()
    try:
        outcome = await recorder.execute(
            "homebrain_resolve_device",
            {"name": "Synthetic Lamp"},
            tool=MCPTool(
                "homebrain_resolve_device", "Resolve named device", {},
                annotations={"effect": ToolEffect.READ.value},
            ),
            evidence_kind="deterministic_targeted_device_resolution",
        )
        receipts = evidence.receipts()
    finally:
        evidence.reset(token)
    assert not outcome.success
    assert len(receipts) == 1
    assert receipts[0]["success"] is False
    assert receipts[0]["supports_live_claim"] is False
    assert receipts[0]["mutates"] is False
