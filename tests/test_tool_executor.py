from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from evidence_recorder import EvidenceRecorder  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_registry import ToolEffect  # noqa: E402


class FakeMCP:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.error is not None:
            raise self.error
        return self.result


def clock(*values):
    sequence = iter(values)
    return lambda: next(sequence)


@pytest.mark.asyncio
async def test_remote_execution_records_one_structured_receipt():
    result = MCPToolResult(
        "hub_read_devices",
        {},
        {},
        "",
        {"devices": []},
    )
    mcp = FakeMCP(result=result)
    evidence = EvidenceRecorder()
    executor = ToolExecutor(mcp, evidence, clock=clock(10.0, 10.125))
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "hub_read_devices",
            {"tool": "hub_list_devices", "args": {}},
            tool=MCPTool(
                "hub_read_devices",
                "Read devices",
                {},
                annotations={"effect": ToolEffect.READ.value},
            ),
            evidence_kind="authoritative_state_snapshot",
        )
        receipts = evidence.receipts()
    finally:
        evidence.reset(token)

    assert execution.success is True
    assert execution.elapsed_ms == 125
    assert execution.result is result
    assert json.loads(execution.content) == {"result": {"devices": []}}
    assert mcp.calls == [
        ("hub_read_devices", {"tool": "hub_list_devices", "args": {}})
    ]
    assert len(receipts) == 1
    assert receipts[0]["evidence_kind"] == "authoritative_state_snapshot"
    assert receipts[0]["effect"] == ToolEffect.READ.value


@pytest.mark.asyncio
async def test_local_handler_is_used_without_calling_remote_gateway():
    mcp = FakeMCP()
    calls = []

    async def local(arguments):
        calls.append(arguments)
        arguments["nested"]["value"] = "handler changed its copy"
        return MCPToolResult("local_tool", arguments, {}, "", {"success": True})

    evidence = EvidenceRecorder()
    executor = ToolExecutor(
        mcp,
        evidence,
        local_handlers={"local_tool": local},
        clock=clock(1.0, 1.001),
    )
    original = {"nested": {"value": "original"}}
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "local_tool",
            original,
            tool=MCPTool(
                "local_tool",
                "Local read",
                {},
                annotations={"effect": ToolEffect.READ.value},
            ),
        )
        receipt = evidence.receipts()[0]
    finally:
        evidence.reset(token)

    assert execution.success is True
    assert mcp.calls == []
    assert calls[0]["nested"]["value"] == "handler changed its copy"
    assert original == {"nested": {"value": "original"}}
    assert execution.arguments == original
    assert receipt["arguments"] == original


@pytest.mark.asyncio
async def test_failed_call_returns_error_content_and_records_failure_once():
    evidence = EvidenceRecorder()
    executor = ToolExecutor(
        FakeMCP(error=RuntimeError("gateway unavailable")),
        evidence,
        clock=clock(2.0, 2.05),
    )
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "hub_read_devices",
            {},
            tool=MCPTool(
                "hub_read_devices",
                "Read devices",
                {},
                annotations={"effect": ToolEffect.READ.value},
            ),
        )
        receipts = evidence.receipts()
    finally:
        evidence.reset(token)

    assert execution.success is False
    assert isinstance(execution.error, RuntimeError)
    assert json.loads(execution.content) == {"error": "gateway unavailable"}
    assert len(receipts) == 1
    assert receipts[0]["success"] is False
    assert receipts[0]["elapsed_ms"] == 50


@pytest.mark.parametrize(
    "data,is_error,expected",
    [
        ({"success": False}, False, False),
        ({"error": "failed"}, False, False),
        ({"result": {"success": False}}, False, False),
        ({"data": {"error": "failed"}}, False, False),
        ({"success": True}, False, True),
        ({}, True, False),
    ],
)
def test_success_detection_preserves_nested_failure_handling(
    data, is_error, expected
):
    result = MCPToolResult("tool", {}, {}, "", data, is_error=is_error)

    assert ToolExecutor.succeeded(result) is expected


def test_payload_bounding_is_preserved_after_extraction():
    executor = ToolExecutor(FakeMCP(), EvidenceRecorder(), max_tool_result_chars=2000)
    result = MCPToolResult("tool", {}, {}, "", {"content": "x" * 5000})

    payload = json.loads(executor.result_payload(result))

    assert payload["truncated"] is True
    assert payload["original_chars"] > 5000


@pytest.mark.asyncio
async def test_mutating_effect_is_preserved_even_when_execution_fails():
    evidence = EvidenceRecorder()
    executor = ToolExecutor(
        FakeMCP(error=RuntimeError("offline")),
        evidence,
        clock=clock(3.0, 3.01),
    )
    tool = MCPTool(
        "hub_update_firmware",
        "Update firmware",
        {},
        annotations={"effect": ToolEffect.SENSITIVE_WRITE.value},
    )
    token = evidence.begin()
    try:
        execution = await executor.execute(
            tool.name,
            {},
            tool=tool,
            supports_live_claim=False,
        )
        receipt = evidence.receipts()[0]
    finally:
        evidence.reset(token)

    assert execution.effect is ToolEffect.SENSITIVE_WRITE
    assert execution.success is False
    assert receipt["mutates"] is True
    assert receipt["effect"] == ToolEffect.SENSITIVE_WRITE.value
    assert receipt["supports_live_claim"] is False


@pytest.mark.asyncio
async def test_execute_redacts_precise_location_before_building_provider_content():
    """Regression test: GPS/address/journey data must never reach execution.content.

    execution.content is what gets appended verbatim as the "tool" role
    message in the provider conversation (see mcp_agent_orchestrator.py),
    including to a cloud provider when ollama_direct_cloud_enabled is set.
    Presence state must still survive so presence questions keep working.
    """

    result = MCPToolResult(
        "hub_read_devices",
        {},
        {},
        "",
        {
            "devices": [
                {
                    "label": "Household Member",
                    "attributes": [
                        {"name": "latitude", "value": "51.4670704"},
                        {"name": "longitude", "value": "-0.0179751"},
                        {"name": "address1", "value": "Home"},
                        {"name": "presence", "value": "present"},
                        {"name": "battery", "value": 37},
                    ],
                }
            ]
        },
    )
    mcp = FakeMCP(result=result)
    evidence = EvidenceRecorder()
    executor = ToolExecutor(mcp, evidence, clock=clock(10.0, 10.05))
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "hub_read_devices",
            {"tool": "hub_list_devices", "args": {}},
            tool=MCPTool(
                "hub_read_devices", "Read devices", {},
                annotations={"effect": ToolEffect.READ.value},
            ),
        )
    finally:
        evidence.reset(token)

    assert "51.4670704" not in execution.content
    assert "-0.0179751" not in execution.content
    payload = json.loads(execution.content)
    attrs = {a["name"]: a["value"] for a in payload["result"]["devices"][0]["attributes"]}
    assert attrs["presence"] == "present"
    assert attrs["battery"] == 37
    assert attrs["latitude"] != "51.4670704"



class SequencedMCP:
    """Fake MCP client that returns a different canned result per
    (name, sub_tool, attribute) combination -- needed to exercise the
    automatic valueStr backfill, which issues a second real call_tool()
    after the first one comes back with a null 'value'."""

    def __init__(self, responses: dict[tuple[str, str], MCPToolResult]):
        self.responses = responses
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        sub_tool = arguments.get("tool", "")
        attribute = (arguments.get("args") or {}).get("attribute", "")
        key = (sub_tool, attribute)
        if key not in self.responses:
            raise AssertionError(f"unexpected call_tool key: {key}")
        return self.responses[key]


@pytest.mark.asyncio
async def test_null_generic_value_is_backfilled_from_valuestr_automatically():
    # Real shape observed on the user's hub for device 7434, "Octopus Meter
    # Current Power": hub_get_device_attribute(attribute='value') returns
    # value=None even though the device has a live reading, which only
    # shows up under valueStr ("231 W"). The model should never have to
    # spend an extra slow round trip guessing this -- the executor should
    # transparently retry and merge it in.
    null_value_result = MCPToolResult(
        "hub_read_devices",
        {"tool": "hub_get_device_attribute", "args": {"deviceId": "7434", "attribute": "value"}},
        {},
        "",
        {"device": "Octopus Meter Current Power", "attribute": "value", "value": None},
    )
    value_str_result = MCPToolResult(
        "hub_read_devices",
        {"tool": "hub_get_device_attribute", "args": {"deviceId": "7434", "attribute": "valueStr"}},
        {},
        "",
        {"device": "Octopus Meter Current Power", "attribute": "valueStr", "valueStr": "231 W"},
    )
    mcp = SequencedMCP({
        ("hub_get_device_attribute", "value"): null_value_result,
        ("hub_get_device_attribute", "valueStr"): value_str_result,
    })
    evidence = EvidenceRecorder()
    executor = ToolExecutor(mcp, evidence, clock=clock(10.0, 10.05, 10.05, 10.1))
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "hub_read_devices",
            {"tool": "hub_get_device_attribute", "args": {"deviceId": "7434", "attribute": "value"}},
            tool=MCPTool(
                "hub_read_devices", "Read devices", {},
                annotations={"effect": ToolEffect.READ.value},
            ),
        )
    finally:
        evidence.reset(token)

    assert execution.success is True
    payload = json.loads(execution.content)
    assert payload["result"]["value"] is None
    assert payload["result"]["valueStr"] == "231 W"
    assert "value_backfill_note" in payload["result"]
    # Exactly one automatic follow-up call, no more.
    assert len(mcp.calls) == 2
    assert mcp.calls[1][1]["args"]["attribute"] == "valueStr"


@pytest.mark.asyncio
async def test_generic_value_backfill_is_skipped_when_value_already_present():
    # A device that DOES report a real numeric 'value' must never trigger
    # the extra valueStr round trip -- only genuinely null readings should.
    result = MCPToolResult(
        "hub_read_devices",
        {"tool": "hub_get_device_attribute", "args": {"deviceId": "9001", "attribute": "value"}},
        {},
        "",
        {"device": "Some Other Sensor", "attribute": "value", "value": 42},
    )
    mcp = FakeMCP(result=result)
    evidence = EvidenceRecorder()
    executor = ToolExecutor(mcp, evidence, clock=clock(10.0, 10.05))
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "hub_read_devices",
            {"tool": "hub_get_device_attribute", "args": {"deviceId": "9001", "attribute": "value"}},
            tool=MCPTool(
                "hub_read_devices", "Read devices", {},
                annotations={"effect": ToolEffect.READ.value},
            ),
        )
    finally:
        evidence.reset(token)

    assert execution.success is True
    payload = json.loads(execution.content)
    assert payload["result"]["value"] == 42
    assert "valueStr" not in payload["result"]
    assert mcp.calls == [
        (
            "hub_read_devices",
            {"tool": "hub_get_device_attribute", "args": {"deviceId": "9001", "attribute": "value"}},
        )
    ]


@pytest.mark.asyncio
async def test_generic_value_backfill_is_skipped_for_non_value_attribute_reads():
    # Only the specific attribute='value' shape should trigger a backfill --
    # unrelated attribute reads (e.g. 'switch') must be left untouched.
    result = MCPToolResult(
        "hub_read_devices",
        {"tool": "hub_get_device_attribute", "args": {"deviceId": "42", "attribute": "switch"}},
        {},
        "",
        {"device": "Some Switch", "attribute": "switch", "value": None},
    )
    mcp = FakeMCP(result=result)
    evidence = EvidenceRecorder()
    executor = ToolExecutor(mcp, evidence, clock=clock(10.0, 10.05))
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "hub_read_devices",
            {"tool": "hub_get_device_attribute", "args": {"deviceId": "42", "attribute": "switch"}},
            tool=MCPTool(
                "hub_read_devices", "Read devices", {},
                annotations={"effect": ToolEffect.READ.value},
            ),
        )
    finally:
        evidence.reset(token)

    payload = json.loads(execution.content)
    assert payload["result"]["value"] is None
    assert "valueStr" not in payload["result"]
    assert len(mcp.calls) == 1


@pytest.mark.asyncio
async def test_generic_value_backfill_swallows_followup_failure_gracefully():
    # If the automatic valueStr follow-up itself errors, the original
    # (null-value) result must still be returned rather than raising.
    null_value_result = MCPToolResult(
        "hub_read_devices",
        {"tool": "hub_get_device_attribute", "args": {"deviceId": "7434", "attribute": "value"}},
        {},
        "",
        {"device": "Octopus Meter Current Power", "attribute": "value", "value": None},
    )
    error_result = MCPToolResult(
        "hub_read_devices",
        {"tool": "hub_get_device_attribute", "args": {"deviceId": "7434", "attribute": "valueStr"}},
        {},
        "boom",
        None,
        is_error=True,
    )
    mcp = SequencedMCP({
        ("hub_get_device_attribute", "value"): null_value_result,
        ("hub_get_device_attribute", "valueStr"): error_result,
    })
    evidence = EvidenceRecorder()
    executor = ToolExecutor(mcp, evidence, clock=clock(10.0, 10.05, 10.05, 10.1))
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "hub_read_devices",
            {"tool": "hub_get_device_attribute", "args": {"deviceId": "7434", "attribute": "value"}},
            tool=MCPTool(
                "hub_read_devices", "Read devices", {},
                annotations={"effect": ToolEffect.READ.value},
            ),
        )
    finally:
        evidence.reset(token)

    assert execution.success is True
    payload = json.loads(execution.content)
    assert payload["result"]["value"] is None
    assert "valueStr" not in payload["result"]
