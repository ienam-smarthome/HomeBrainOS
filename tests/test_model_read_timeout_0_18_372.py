"""v0.18.372: model-selected read waits fail independently of 180s request.

Tests are fully simulated: no Ollama, Home Assistant or Hubitat calls.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))
import tool_executor as target  # noqa: E402
from app import RequestCoordinator  # noqa: E402
from evidence_recorder import EvidenceRecorder  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from tool_registry import ToolEffect  # noqa: E402


@pytest.fixture
def model_read(monkeypatch):
    monkeypatch.setattr(target, "_MODEL_READ_WAIT_SECONDS", 0.016)
    monkeypatch.setattr(target, "claim_model_tool_call", lambda *_: 1)
    monkeypatch.setattr(
        target, "register_model_tool_execution", lambda **_: True,
    )


@pytest.mark.asyncio
async def test_stalled_remote_model_read_gets_failure_receipt_not_proof(model_read):
    cancelled = asyncio.Event()

    class NeverCompletes:
        async def call_tool(self, *_):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    evidence = EvidenceRecorder()
    executor = target.ToolExecutor(NeverCompletes(), evidence)
    tool = MCPTool("hub_read_devices", "Read", {},
                   annotations={"effect": ToolEffect.READ.value})
    token = evidence.begin()
    try:
        outcome = await asyncio.wait_for(
            executor.execute("hub_read_devices", {
                "tool": "hub_get_device", "args": {"deviceId": "777"},
            }, tool=tool), timeout=1,
        )
        rows = evidence.receipts()
    finally:
        evidence.reset(token)

    assert cancelled.is_set()
    assert not outcome.success
    assert isinstance(outcome.error, TimeoutError)
    assert "timed out" in json.loads(outcome.content)["error"].lower()
    assert len(rows) == 1
    assert rows[0]["success"] is False
    assert rows[0]["effect"] == "read"
    assert rows[0]["mutates"] is False
    assert rows[0]["supports_live_claim"] is False
    assert "source result" in rows[0]["summary"]


@pytest.mark.asyncio
async def test_stalled_local_model_read_is_also_bounded(model_read):
    cancelled = asyncio.Event()
    async def local(args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    evidence = EvidenceRecorder()
    executor = target.ToolExecutor(None, evidence, local_handlers={
        "homebrain_resolve_device": local,
    })
    tool = MCPTool("homebrain_resolve_device", "Read", {},
                   annotations={"effect": ToolEffect.READ.value})
    token = evidence.begin()
    try:
        result = await asyncio.wait_for(
            executor.execute("homebrain_resolve_device",
                             {"name": "Example"}, tool=tool), timeout=1,
        )
        receipts = evidence.receipts()
    finally:
        evidence.reset(token)
    assert cancelled.is_set()
    assert not result.success
    assert len(receipts) == 1 and receipts[0]["success"] is False


@pytest.mark.asyncio
async def test_deterministic_read_not_subject_to_model_only_ceiling(model_read):
    # Host reads do not participate in model tool round budgeting.
    # The normal overall coordinator deadline still applies to them.
    class SlowRemote:
        async def call_tool(self, name, arguments):
            await asyncio.sleep(0.035)
            return MCPToolResult(name, arguments, {}, "", {"success": True})

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(target, "claim_model_tool_call", lambda *_: 0)
    try:
        ex = target.ToolExecutor(SlowRemote(), EvidenceRecorder())
        result = await ex.execute(
            "hub_read_devices", {"tool": "hub_get_device",
                                 "args": {"deviceId": "100"}},
            tool=MCPTool("hub_read_devices", "Read", {},
                         annotations={"effect": ToolEffect.READ.value}),
        )
        assert result.success is True
    finally:
        monkeypatch.undo()


@pytest.mark.asyncio
async def test_confirmed_write_is_not_cancelled_by_read_deadline(model_read):
    invoked = 0
    async def local_write(arguments):
        nonlocal invoked
        invoked += 1
        await asyncio.sleep(0.034)
        return MCPToolResult("hub_update_firmware", arguments, {}, "",
                             {"success": True})

    executor = target.ToolExecutor(None, EvidenceRecorder(), local_handlers={
        "hub_update_firmware": local_write,
    })
    tool = MCPTool("hub_update_firmware", "Update", {},
                   annotations={"effect": ToolEffect.SENSITIVE_WRITE.value})
    result = await executor.execute("hub_update_firmware", {}, tool=tool)
    assert result.success
    assert invoked == 1
    assert result.effect.mutates


@pytest.mark.asyncio
async def test_request_timeout_displays_exact_log_request_id_without_verified_data():
    coordinator = RequestCoordinator()
    async def stuck():
        await asyncio.Event().wait()

    request_id = "q2-telemetry-lookup-abc123"
    with pytest.raises(HTTPException) as caught:
        await coordinator.run(
            "q2-telemetry-test", stuck(), request_id=request_id,
            deadline_seconds=0.065,
        )
    assert caught.value.status_code == 504
    assert request_id in caught.value.detail
    assert "No verified read-only results" in caught.value.detail
    await coordinator.close()
