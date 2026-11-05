"""Live-shape regression: exact owned devices, not Rule Machine exclusions.

Source data is synthetic. No Hubitat, Home Assistant or cloud model is called.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from evidence_recorder import EvidenceRecorder
from mcp_client import MCPTool, MCPToolResult
from mcp_agent_orchestrator import UnifiedMCPAgent
from owned_device_inventory_source import (
    is_explicit_owned_device_inventory_request,
    owned_device_coverage,
    read_owned_virtual_device_inventory,
)
from shared_investigation_completion import apply_shared_investigation_completion

PROMPT = (
    'Read-only inventory of MCP-created virtual devices ONLY.\n\n'
    'Call hub_list_devices with scope="owned" and format="detailed" '
    'through an authorized read-only MCP gateway. Follow all returned '
    'nextCursor pages.\n\n'
    'Report the total device count and whether the inventory is complete. '
    'For every Virtual Switch, return its device ID, label, driverType, '
    'driverNamespace and mcpManaged flag where available.\n\n'
    'If the source fails or returns incomplete data, show the actual MCP '
    'error. Do not assume an empty inventory.\n\n'
    'Do not call any Rule Machine operation. Do not create, modify, execute '
    'or delete any rule, device, backup or setting.'
)


class NoModel:
    async def chat(self, *args, **kwargs):
        raise AssertionError("Exact read must not start model planning")


class FakeMCP:
    def __init__(self, pages=None, *, direct=False, error=False):
        self.calls = []
        self.direct = direct
        self.error = error
        self.pages = pages if pages is not None else {
            "0": {
                "devices": [
                    {"id": "8090", "label": "BAT Virtual Switch",
                     "driver": "Virtual Switch", "driverNamespace": "hubitat",
                     "mcpManaged": True},
                ],
                "count": 1, "total": 1, "offset": 0, "hasMore": False,
            }
        }

    async def list_tools(self):
        return [MCPTool("hub_list_devices" if self.direct else "hub_read_devices",
                        "Read devices", {"type": "object"})]

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        if self.direct:
            assert gateway == "hub_list_devices"
            query = args
        else:
            assert gateway == "hub_read_devices"
            assert args["tool"] == "hub_list_devices"
            query = args["args"]
        assert query["scope"] == "owned"
        assert query["format"] == "detailed"
        assert query["limit"] == 20
        if self.error:
            return MCPToolResult(gateway, args, {}, "", {
                "success": False, "error": {"code": "DENIED", "message": "read not allowed"},
            }, True)
        page = self.pages.get(query["cursor"])
        assert page is not None, "Must not retry or invent an unknown cursor"
        return MCPToolResult(gateway, args, {}, "", page)


def test_requested_device_only_inventory_has_exclusive_owned_scope():
    assert is_explicit_owned_device_inventory_request(PROMPT)
    assert not is_explicit_owned_device_inventory_request(
        'Do not call hub_list_devices scope="owned" format="detailed"; Virtual devices ONLY')
    assert not is_explicit_owned_device_inventory_request(
        'List Rule Machine parent and owned virtual devices: '
        'hub_list_devices scope="owned" format="detailed"')


@pytest.mark.asyncio
async def test_live_prompt_routes_only_exact_owned_device_read_and_resolves():
    mcp = FakeMCP()
    agent = UnifiedMCPAgent(mcp, "test-key", "gemma4:31b", ai_client=NoModel())
    result = await agent.process_user_request_result(
        PROMPT, session_id="owned-devices-20261103")
    assert result.request_class == "live-read"
    assert len(mcp.calls) == 1
    assert mcp.calls[0][1]["args"]["scope"] == "owned"
    assert "BAT Virtual Switch" in result.message
    assert "Complete owned-device inventory: 1 of 1" in result.message
    assert "Rule Machine parent identity was not checked" in result.message
    assert "Rule Machine inventory — read-only" not in result.message
    assert all(row["effect"] == "read" and not row["mutates"]
               for row in result.evidence)
    assert any(row["evidence_kind"] == "typed_owned_device_inventory"
               for row in result.evidence)
    assessed = apply_shared_investigation_completion(result, PROMPT)
    assert assessed.investigation_coverage["questionResolved"] is True
    assert assessed.investigation_coverage["domain"] == "owned_virtual_device_inventory"
    assert assessed.metrics["outcome"] == "success"
    assert assessed.message == result.message


@pytest.mark.asyncio
async def test_bounded_pagination_follows_cursor_and_preserves_total():
    pages = {
        "0": {"devices": [{"id": "8090", "label": "Test A",
                           "driver": "Virtual Switch", "mcpManaged": True}],
              "count": 1, "total": 2, "offset": 0,
              "hasMore": True, "nextCursor": "1"},
        "1": {"devices": [{"id": "8091", "label": "Test B",
                           "driver": "Virtual Switch", "mcpManaged": True}],
              "count": 1, "total": 2, "offset": 1,
              "hasMore": False},
    }
    mcp = FakeMCP(pages)
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        msg, data = await read_owned_virtual_device_inventory(
            mcp, recorder, available_names={"hub_read_devices"})
        assert len(mcp.calls) == 2
        assert data["inventoryComplete"] is True
        assert data["returnedCount"] == data["sourceTotal"] == 2
        assert msg.count("mcpManaged=true") == 2
        assert owned_device_coverage(PROMPT, recorder.receipts())["questionResolved"]
    finally:
        recorder.reset(token)


@pytest.mark.asyncio
async def test_complete_zero_owned_devices_is_not_confused_with_failed_read():
    mcp = FakeMCP({"0": {
        "devices": [], "count": 0, "total": 0,
        "offset": 0, "hasMore": False,
    }}, direct=True)
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        msg, data = await read_owned_virtual_device_inventory(
            mcp, recorder, available_names={"hub_list_devices"})
        assert data["inventoryComplete"] is True
        assert data["returnedCount"] == 0
        assert "No Virtual Switch driver was identified" in msg
        assert len(mcp.calls) == 1
        assert mcp.calls[0][0] == "hub_list_devices"
    finally:
        recorder.reset(token)


@pytest.mark.asyncio
async def test_actual_source_error_does_not_claim_empty_or_success():
    mcp = FakeMCP(error=True)
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        msg, data = await read_owned_virtual_device_inventory(
            mcp, recorder, available_names={"hub_read_devices"})
        assert "DENIED" in msg
        assert "no empty-inventory claim" in msg
        assert data["inventoryComplete"] is False
        assessment = owned_device_coverage(PROMPT, recorder.receipts())
        assert assessment["questionResolved"] is False
        wrapped = apply_shared_investigation_completion(SimpleNamespace(
            route="unified-mcp-agent", request_class="live-read",
            message=msg, evidence=recorder.receipts(),
            metrics={"outcome": "success", "counters": {"tool_calls": 1}},
        ), PROMPT)
        assert wrapped.metrics["outcome"] == "unresolved"
        assert wrapped.message == msg
    finally:
        recorder.reset(token)


@pytest.mark.parametrize("bad_page", [
    {"devices": [], "count": 0, "total": 2, "offset": 0, "hasMore": False},
    {"devices": [{"id": "90", "driver": "Virtual Switch"}],
     "count": 1, "total": 1, "offset": 0, "hasMore": False},
    {"devices": [], "count": 0, "total": 0, "offset": 0, "hasMore": True},
    {"devices": [], "count": 0, "total": 0, "offset": 1, "hasMore": False},
    {"devices": [{"id": "90", "driver": "Virtual Switch", "mcpManaged": True,
                  "metadataUnavailable": True}],
     "count": 1, "total": 1, "offset": 0, "hasMore": False},
])
@pytest.mark.asyncio
async def test_unproven_pages_or_ownership_fail_closed(bad_page):
    mcp = FakeMCP({"0": bad_page})
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        msg, data = await read_owned_virtual_device_inventory(
            mcp, recorder, available_names={"hub_read_devices"})
        c = owned_device_coverage(PROMPT, recorder.receipts())
        assert c["questionResolved"] is False
        assert "not fully verified" in msg
    finally:
        recorder.reset(token)


@pytest.mark.asyncio
async def test_missing_read_gateway_does_not_guess_an_empty_inventory():
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        msg, data = await read_owned_virtual_device_inventory(
            FakeMCP(), recorder, available_names=set())
        assert "unavailable" in msg
        assert data["inventoryComplete"] is False
        assert owned_device_coverage(PROMPT, recorder.receipts())["questionResolved"] is False
    finally:
        recorder.reset(token)
