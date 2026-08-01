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
