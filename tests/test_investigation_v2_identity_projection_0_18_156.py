"""v0.18.156: verify identity-only paging and explain controller-read blockers.

All MCP responses are synthetic. No live device, model provider or writes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import HubitatMCPClient, MCPTool, MCPToolResult
from investigation_v2.evidence import build_case_file
from investigation_v2.receipt_projection import project_read_receipt
from investigation_v2.source_identity import source_configuration_proposals
from investigation_v2.test_service import resolve_verified_device_subjects


@pytest.mark.asyncio
async def test_minimal_live_identity_inventory_uses_no_state_or_capabilities():
    client = HubitatMCPClient("http://127.0.0.1:1/mcp", max_concurrent_calls=2)
    calls = []

    async def list_tools(refresh=False):
        return [MCPTool("hub_read_devices", "", {"type": "object"})]

    async def call_tool(name, arguments):
        assert name == "hub_read_devices"
        args = arguments["args"]
        calls.append(args)
        assert args["detailed"] is False
        assert "attributes" not in args["fields"]
        assert "currentStates" not in args["fields"]
        assert "commands" not in args["fields"]
        assert "capabilities" not in args["fields"]
        assert "lastActivity" not in args["fields"]
        offset = args["offset"]
        count = 50 if offset == 0 else 1
        items = [{"id": str(offset+i+1),
                  "label": f"Device {offset+i+1}",
                  "name": "Generic Smart Device"} for i in range(count)]
        return MCPToolResult(
            name, arguments, raw={}, text="NOT_TRUSTED",
            data={"devices": items, "total": 51,
                  "hasMore": offset == 0,
                  "nextOffset": 50 if offset == 0 else None},
            is_error=False,
        )

    async def no_fallback(*args, **kwargs):
        raise AssertionError("Verified identity projection must not need fallback")

    client.list_tools = list_tools
    client.call_tool = call_tool
    client.get_cached_devices = no_fallback
    try:
        devices, provenance = await client.get_audit_devices(identity_only=True)
    finally:
        await client.close()
    assert len(devices) == 51
    assert provenance["projection"] == "identity_only"
    assert provenance["complete"] is True
    assert provenance["mode"] == "bounded_parallel_pages"
    assert len(calls) == 2
    ids, matches, method = resolve_verified_device_subjects(
        "Investigate Device 51", devices)
    assert ids == ("51",)
    assert matches == [{"id": "51", "label": "Device 51"}]
    assert method == "question"


@pytest.mark.asyncio
async def test_incomplete_identity_inventory_remains_explicitly_unverified():
    client = HubitatMCPClient("http://127.0.0.1:1/mcp")

    async def list_tools(refresh=False):
        return [MCPTool("hub_read_devices", "", {"type": "object"})]

    async def call_tool(name, arguments):
        return MCPToolResult(
            name, arguments, raw={}, text="", data={
                "devices": [{"id": "7103", "label": "Bedroom 3 Mesh"}],
                "total": 2, "hasMore": False,
            })

    async def fallback(*args, **kwargs):
        return [{"id": "7103", "label": "Bedroom 3 Mesh", "attributes": {}}]

    client.list_tools = list_tools
    client.call_tool = call_tool
    client.get_cached_devices = fallback
    try:
        devices, provenance = await client.get_audit_devices(identity_only=True)
    finally:
        await client.close()
    assert devices and provenance["complete"] is False
    assert provenance["source"] == "full_detailed_fallback"
    assert provenance["projection"] == "full"


def command_case():
    args = {"tool": "hub_list_device_events",
            "args": {"deviceId": "7103", "limit": 50}}
    result = MCPToolResult("hub_read_devices", args, raw={}, text="",
        data={"deviceId": "7103", "events": [{
            "name": "command-on", "type": "command", "deviceId": "7103",
            "date": "2026-10-24T20:51:12+00:00",
            "producedBy": {"id": "3103"},
        }]}, is_error=False)
    receipt = project_read_receipt("hub_read_devices", args, result,
                                  source_request_id="attested-command")
    case = build_case_file("Why is Bedroom 3 Mesh offline?", [receipt])
    case.app_identities["3103"] = "Ikea Rodret Dimmer"
    return case


def app_gateway(ops, read_only=True, arg_properties=None):
    return MCPTool("hub_read_apps_code", "Read-only app gateway", {
        "type": "object",
        "properties": {
            "tool": {"type": "string", "enum": ops},
            "args": {"type": "object", "properties": (
                arg_properties if arg_properties is not None else
                {"appId": {"type": "string"}}),
                "required": ["appId"], "additionalProperties": False},
        },
        "required": ["tool", "args"], "additionalProperties": False,
    }, annotations={"readOnlyHint": read_only, "mutates": not read_only})


@pytest.mark.parametrize("tool,reason", [
    (app_gateway(["hub_list_apps"]), "operation_not_in_live_enum"),
    (app_gateway(["hub_get_app_config"], read_only=False), "safe_read_gateway_unavailable"),
    (app_gateway(["hub_get_app_config"], arg_properties={}), "app_id_missing_from_live_schema"),
])
def test_controller_read_skip_explains_missing_live_permission(tool, reason):
    diagnostics = []
    proposals = source_configuration_proposals(
        [tool], command_case(), diagnostics=diagnostics)
    assert proposals == []
    assert diagnostics == [{"stage": "controller_config", "reason": reason}]


def test_controller_attested_issuer_proposed_even_when_named():
    diag = []
    proposals = source_configuration_proposals(
        [app_gateway(["hub_get_app_config"])],
        command_case(), diagnostics=diag)
    assert len(proposals) == 1
    assert proposals[0]["arguments"]["args"] == {"appId": "3103"}
    assert diag == [{"stage": "controller_config",
                     "status": "verified_issuer_proposal", "issuer_id": "3103"}]


def test_endpoint_retrieves_identity_then_full_only_when_scope_needs_it():
    code = (APP / "app.py").read_text()
    section = code.split("async def v2_test(", 1)[1].split(
        '@app.post("/api/chat")', 1)[0]
    assert "get_audit_devices(\n                    identity_only=True)" in section
    assert 'inventory_provenance.get("projection")=="identity_only"' in section
    assert "resolve_verified_device_subjects(" in section
    assert "full_inventory_ms" in section
    assert "planning_timeout_seconds=15.0" in section
    assert "agent.process_user_request_result" not in section
