"""v0.18.171: a complete exact-label filtered Hubitat result can prove one read-only target."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool, MCPToolResult
from investigation_v2.targeted_status import (
    explicit_current_device_name, read_filtered_target_identity,
)

QUESTION = ("Read the current switch state and brightness level of "
            "Livingroom Light 2 directly from Hubitat. Do not change anything.")


def gateway(*, filter_enabled=True):
    args = {
        "deviceId": {"type": "string"},
        "mode": {"type": "string", "enum": ["status"]},
        "fields": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer"},
        "offset": {"type": "integer"},
        "detailed": {"type": "boolean"},
    }
    if filter_enabled:
        args["labelFilter"] = {"type": "string"}
    return MCPTool("hub_read_devices", "Read Hubitat devices",
        {"type": "object", "properties": {
            "tool": {"type": "string", "enum": ["hub_list_devices", "hub_get_device"]},
            "args": {"type": "object", "properties": args,
                     "additionalProperties": False},
        }, "required": ["tool", "args"], "additionalProperties": False},
        annotations={"readOnlyHint": True, "mutates": False})


class MCP:
    def __init__(self, *, page=None, filter_enabled=True):
        self.page = (page if page is not None else {
            "devices": [{"id": "7828", "label": "Livingroom Light 2",
                         "name": "Generic dimmer", "room": "Living Room"}],
            "total": 1, "hasMore": False, "nextOffset": None,
        })
        self.tools = [gateway(filter_enabled=filter_enabled)]
        self.calls = []

    async def list_tools(self):
        return self.tools

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        operation = arguments["tool"]
        if operation == "hub_list_devices":
            return MCPToolResult(name, arguments, {}, "", self.page)
        if operation == "hub_get_device":
            return MCPToolResult(name, arguments, {}, "",
                {"device": {"id": "7828", "attributes": [
                    {"name": "switch", "value": "off"},
                    {"name": "level", "value": 30},
                ]}})
        raise AssertionError(f"Unexpected operation: {operation}")


def test_only_exact_factual_one_device_name_extracted():
    assert explicit_current_device_name(QUESTION) == "Livingroom Light 2"
    assert explicit_current_device_name("Turn on Livingroom Light 2.") is None
    assert explicit_current_device_name(
        "Why did Livingroom Light 2 turn off and who did it?") is None
    assert explicit_current_device_name(
        "Read the current switch state and brightness level of "
        "Livingroom Light 2 and Hallway Light 1 directly from Hubitat. "
        "Do not change anything.") is None


@pytest.mark.asyncio
async def test_complete_filtered_identity_is_scoped_source_verification():
    m = MCP()
    diag = {}
    result = await read_filtered_target_identity(m, "Livingroom Light 2",
                                                 diagnostics=diag)
    assert result is not None
    identities, provenance = result
    assert identities[0]["id"] == "7828"
    assert provenance["complete"] is True
    assert provenance["home_inventory_complete"] is False
    assert provenance["projection"] == "filtered_identity_only"
    assert diag["identity_lookup"] == "filtered_unique_exact_label"
    assert m.calls[0][1]["args"]["labelFilter"] == "Livingroom Light 2"
    assert m.calls[0][1]["args"]["fields"] == ["id", "name", "label", "room"]


@pytest.mark.asyncio
@pytest.mark.parametrize("page", [
    {"devices": [{"id": "7828", "label": "Livingroom Light 2"}]},
    {"devices": [{"id": "7828", "label": "Livingroom Light 2"}],
     "total": 2, "hasMore": True, "nextOffset": 50},
    {"devices": [{"id": "7828", "label": "Livingroom Light 2"},
                 {"id": "9999", "label": "Livingroom Light 2"}],
     "total": 2, "hasMore": False},
    {"devices": [{"id": "7828", "label": "Livingroom Light 2"}],
     "total": 204, "hasMore": False},
    {"devices": [{"id": "7828", "label": "Wrong Device"}],
     "total": 1, "hasMore": False},
    {"devices": [{"id": "not-an-id", "label": "Livingroom Light 2"}],
     "total": 1, "hasMore": False},
])
async def test_no_scoped_identity_from_partial_duplicate_unfiltered_or_wrong_page(page):
    m = MCP(page=page)
    diag = {}
    assert await read_filtered_target_identity(
        m, "Livingroom Light 2", diagnostics=diag) is None
    assert diag["identity_lookup"] in (
        "filtered_coverage_unverified", "filtered_identity_mismatch")


@pytest.mark.asyncio
async def test_legacy_gateway_uses_production_read_contract_with_strict_source_coverage():
    m = MCP(filter_enabled=False)
    diag = {}
    result = await read_filtered_target_identity(
        m, "Livingroom Light 2", diagnostics=diag)
    assert result is not None
    assert result[0][0]["id"] == "7828"
    assert diag["identity_lookup"] == "filtered_unique_exact_label"
    assert diag["filter_contract"] == "host_allowlisted_production_read_contract"
    assert len(m.calls) == 1
    assert m.calls[0][1]["tool"] == "hub_list_devices"
    assert m.calls[0][1]["args"]["labelFilter"] == "Livingroom Light 2"


@pytest.mark.asyncio
async def test_legacy_filter_ignored_cannot_prove_a_target():
    m = MCP(filter_enabled=False, page={
        "devices": [{"id": "7828", "label": "Livingroom Light 2"}],
        "total": 204, "hasMore": True, "nextOffset": 50,
    })
    diagnostics = {}
    assert await read_filtered_target_identity(
        m, "Livingroom Light 2", diagnostics=diagnostics) is None
    assert diagnostics["filter_contract"] == "host_allowlisted_production_read_contract"
    assert diagnostics["identity_lookup"] == "filtered_coverage_unverified"


@pytest.mark.asyncio
async def test_legacy_contract_never_opens_a_write_or_undeclared_operation():
    m = MCP(filter_enabled=False)
    m.tools[0].annotations["readOnlyHint"] = False
    diag = {}
    assert await read_filtered_target_identity(
        m, "Livingroom Light 2", diagnostics=diag) is None
    assert diag["identity_lookup"] == "filtered_gateway_unavailable"
    assert not m.calls
    m = MCP(filter_enabled=False)
    m.tools[0].input_schema["properties"]["tool"]["enum"] = ["hub_get_device"]
    diag = {}
    assert await read_filtered_target_identity(
        m, "Livingroom Light 2", diagnostics=diag) is None
    assert diag["identity_lookup"] == "filtered_gateway_unavailable"
    assert not m.calls


def test_http_fast_scoped_read_never_uses_204_device_inventory(monkeypatch, tmp_path):
    options = tmp_path / "options.json"
    options.write_text(json.dumps({
        "investigation_v2_testing_enabled": True,
        "investigation_v2_test_token": "read-only-filtered-identity-123456789",
        "morning_health_check_enabled": False,
        "one_time_rule_cleanup_enabled": False,
    }), encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(options))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    m = MCP()
    async def forbid_inventory(*_args, **_kwargs):
        raise AssertionError("unfiltered inventory should not run")
    async def forbid_model(*_args, **_kwargs):
        raise AssertionError("model should not run for exact factual status")
    monkeypatch.setattr(module.mcp, "recent_verified_audit_identities", lambda: None)
    monkeypatch.setattr(module.mcp, "get_audit_devices", forbid_inventory)
    monkeypatch.setattr(module.mcp, "list_tools", m.list_tools)
    monkeypatch.setattr(module.mcp, "call_tool", m.call_tool)
    monkeypatch.setattr(module, "semantic_plan", forbid_model)
    with TestClient(module.app) as client:
        response = client.post("/api/v2/test",
            json={"question": QUESTION, "explicit_opt_in": True},
            headers={"X-HomeBrain-V2-Test-Token": "read-only-filtered-identity-123456789",
                     "X-HomeBrain-V2-Request": "read-only"})
    assert response.status_code == 200, response.text
    body = response.json()
    diag = body["semantic_diagnostics"]
    assert diag["identity_scope"] == "exact_label"
    assert diag["home_inventory_complete"] is False
    assert diag["full_inventory_ms"] == 0
    assert diag["planning_ms"] == 0
    assert diag["target_id"] == "7828"
    assert diag["targeted_status"]["identity_lookup"] == "filtered_unique_exact_label"
    assert body["inventory_query"]["inventory_scope"] == "exact_label"
    assert body["inventory_query"]["home_inventory_complete"] is False
    assert body["inventory_query"]["reported_device_values"][0]["reported_attributes"] == {
        "switch": "off", "level": 30}
    assert [request["tool"] for _, request in m.calls] == [
        "hub_list_devices", "hub_get_device"]
