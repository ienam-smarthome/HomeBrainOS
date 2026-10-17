"""Claude tool schemas must fail closed, and upstream bad-tool indices must be identifiable."""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from anthropic_transport import (
    AnthropicMessagesTransport, ClaudeToolSchemaError,
    convert_tools, describe_anthropic_http_error,
)


def declared(name="hub_read_devices", schema=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "Read real device status",
            "parameters": schema if schema is not None else {
                "type": "object",
                "properties": {"deviceId": {"type": "string"}},
                "required": ["deviceId"],
                "additionalProperties": False,
            },
        },
    }


@pytest.mark.parametrize("bad", [
    5,
    {},
    {"type": "array", "items": {"type": "string"}},
    {"type": "object", "properties": []},
    {"type": "object", "required": "deviceId"},
])
def test_invalid_provider_root_schema_rejected_before_any_http_or_mcp(bad):
    schema = bad
    item = declared()
    item["function"]["parameters"] = schema
    with pytest.raises(ClaudeToolSchemaError, match="no provider request was sent"):
        convert_tools([item])


@pytest.mark.parametrize("tool_name", [
    "with periods", "hub/unsafe", "", "z" * 129,
])
def test_invalid_tool_name_rejected_locally(tool_name):
    with pytest.raises(ClaudeToolSchemaError, match="invalid tool name"):
        convert_tools([declared(tool_name)])


def test_duplicate_names_blocked_locally_without_tool_renaming():
    with pytest.raises(ClaudeToolSchemaError, match="repeats"):
        convert_tools([declared(), declared()])


def test_good_tool_schema_preserves_exact_permissions_and_parameter_constraints():
    tool = declared()
    result = convert_tools([tool])
    assert result[0]["name"] == "hub_read_devices"
    assert result[0]["input_schema"] == tool["function"]["parameters"]
    assert result[0]["input_schema"]["required"] == ["deviceId"]
    assert result[0]["input_schema"]["additionalProperties"] is False
    assert tool["function"]["parameters"]["properties"]["deviceId"]["type"] == "string"


def make_error(message):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(
        400, request=request, json={
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": message,
            },
        },
    )
    return httpx.HTTPStatusError(
        "Anthropic request rejected", request=request, response=response,
    )


@pytest.mark.parametrize("path", [
    "tools.1.input_schema should be an object",
    "tools[1].input_schema contains unsupported fields",
    "tools.1.custom.input_schema must be JSON Schema",
])
def test_exact_provider_tool_index_maps_to_safe_local_tool_name_only(path):
    exc = make_error(path + " sk-ant-FORBIDDEN other-user-private-text")
    exc._homebrain_claude_tool_names = ("homebrain_read_devices", "hub_read_devices")
    status, msg, _, error_type, reason = describe_anthropic_http_error(exc)
    assert (status, error_type, reason) == (400, "invalid_request_error", "tool-schema")
    assert "tool=hub_read_devices" in msg
    assert "tool_index=1" in msg
    assert "sk-ant-FORBIDDEN" not in msg
    assert "other-user-private-text" not in msg
    assert path not in msg


def test_unmapped_or_out_of_range_provider_tool_errors_do_not_leak_name_or_body():
    exc = make_error("tools.999.input_schema wrong: private SECRET")
    exc._homebrain_claude_tool_names = ("hub_read_devices",)
    _, msg, _, _, _ = describe_anthropic_http_error(exc)
    assert "tool_index=" not in msg
    assert "SECRET" not in msg


@pytest.mark.asyncio
async def test_http_400_error_has_original_declared_tool_index_after_real_request():
    class Response:
        def raise_for_status(self):
            raise make_error("tools[1].input_schema has invalid format: SECRET")
    class Client:
        def __init__(self):
            self.calls = []
        async def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()
    client = Client()
    claude = AnthropicMessagesTransport(
        client, api_key="secret", model="claude-sonnet-4-6", timeout=30,
    )
    with pytest.raises(httpx.HTTPStatusError) as caught:
        await claude.chat(
            [{"role": "user", "content": "Read device"}],
            [declared("homebrain_read_devices"), declared("hub_read_devices")],
        )
    assert len(client.calls) == 1
    assert caught.value._homebrain_claude_tool_names == (
        "homebrain_read_devices", "hub_read_devices",
    )
    assert "tool=hub_read_devices" in describe_anthropic_http_error(caught.value)[1]


@pytest.mark.asyncio
async def test_bad_declared_schema_means_zero_external_requests():
    class Client:
        async def post(self, *args, **kwargs):
            raise AssertionError("A malformed schema cannot reach Anthropic")
    claude = AnthropicMessagesTransport(
        Client(), api_key="secret", model="claude-sonnet-4-6", timeout=30,
    )
    tool = declared()
    tool["function"]["parameters"] = {"type": "array"}
    with pytest.raises(ClaudeToolSchemaError):
        await claude.chat([{"role": "user", "content": "Hello"}], [tool])
