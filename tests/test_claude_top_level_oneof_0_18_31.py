"""v0.18.31 — Claude root oneOf projection and execution-time preservation."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from anthropic_transport import (
    AnthropicMessagesTransport, ClaudeToolSchemaError, convert_tools,
)
from tool_registry import control_devices_tool
from tool_discovery_catalog import ToolDiscoveryCatalog


def control():
    source = control_devices_tool()
    return ToolDiscoveryCatalog.tool_schema(source)


def test_live_rejected_tool_no_longer_contains_root_oneof_on_claude_wire():
    original = control()
    snapshot = deepcopy(original)
    source = original["function"]["parameters"]
    assert source["oneOf"] == [
        {"required": ["room"]}, {"required": ["device_names"]},
    ]
    result = convert_tools([original])
    sent = result[0]
    assert sent["name"] == "homebrain_control_devices"
    assert "oneOf" not in sent["input_schema"]
    assert "allOf" not in sent["input_schema"]
    assert "anyOf" not in sent["input_schema"]
    assert sent["input_schema"]["required"] == ["device_kind", "command"]
    assert sent["input_schema"]["additionalProperties"] is False
    assert sent["input_schema"]["properties"] == source["properties"]
    assert "exactly ONE" in sent["description"]
    assert "`room`" in sent["description"]
    assert "`device_names`" in sent["description"]
    assert original == snapshot


@pytest.mark.parametrize("schema", [
    {"type": "object", "properties": {"x": {"type": "string"}},
     "oneOf": [{"required": ["x"]}, {"properties": {"x": {"type": "string"}}}]},
    {"type": "object", "properties": {"x": {"type": "string"}},
     "oneOf": [{"required": ["x"]}, {"required": ["not_declared"]}]},
    {"type": "object", "properties": {"x": {"type": "string"}},
     "anyOf": [{"required": ["x"]}]},
    {"type": "object", "properties": {"x": {"type": "string"}},
     "allOf": [{"required": ["x"]}]},
])
def test_unsafe_root_compositions_fail_closed_not_relaxed(schema):
    tool = control()
    tool["function"]["parameters"] = schema
    with pytest.raises(ClaudeToolSchemaError, match="no provider request was sent"):
        convert_tools([tool])


class Response:
    def __init__(self, data):
        self.data = data
    def raise_for_status(self):
        return None
    def json(self):
        return self.data


class Client:
    def __init__(self, data):
        self.data = data
        self.requests = []
    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return Response(self.data)


def model_tool(arguments):
    return {
        "type": "tool_use", "id": "toolu_fake",
        "name": "homebrain_control_devices", "input": arguments,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("args", [
    {"device_kind": "switch", "command": "off", "room": "Bedroom 3",
     "device_names": ["Bedroom 3 Mesh"]},
    {"device_kind": "switch", "command": "off"},
])
async def test_generated_control_violating_original_oneof_cannot_reach_executor(args):
    client = Client({"content": [model_tool(args)]})
    transport = AnthropicMessagesTransport(
        client, api_key="fake", model="claude-sonnet-4-6", timeout=20,
    )
    with pytest.raises(ClaudeToolSchemaError, match="no Hubitat command was sent"):
        await transport.chat([{"role": "user", "content": "Switch off"}], [control()])
    assert len(client.requests) == 1
    wire_tool = client.requests[0][1]["json"]["tools"][0]
    assert "oneOf" not in wire_tool["input_schema"]


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [
    {"room": "Bedroom 3"},
    {"device_names": ["Bedroom 3 Mesh"]},
])
async def test_valid_either_or_control_reaches_existing_policy_gate_unchanged(target):
    args = {"device_kind": "switch", "command": "off", **target}
    client = Client({"content": [model_tool(args)]})
    transport = AnthropicMessagesTransport(
        client, api_key="fake", model="claude-sonnet-4-6", timeout=20,
    )
    result = await transport.chat(
        [{"role": "user", "content": "Switch off"}], [control()],
    )
    assert result["tool_calls"][0]["function"]["arguments"] == args
    # Transport only returns a proposal; never executes a Hubitat command.
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_real_readonly_incident_catalog_schema_converts_without_root_combinator():
    source = control()
    declared = [
        {"type": "function", "function": {
            "name": "homebrain_read_devices", "description": "Read status",
            "parameters": {"type": "object", "properties": {
                "deviceId": {"type": "string"},
            }},
        }},
        source,
    ]
    converted = convert_tools(declared)
    assert len(converted) == 2
    assert [entry["name"] for entry in converted] == [
        "homebrain_read_devices", "homebrain_control_devices",
    ]
    assert converted[1]["input_schema"]["properties"]["command"]["enum"] == [
        "on", "off", "toggle", "set_level", "adjust_level",
        "set_temperature", "adjust_temperature",
    ]
