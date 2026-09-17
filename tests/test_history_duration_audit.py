from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from evidence_recorder import EvidenceRecorder  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_registry import ToolEffect  # noqa: E402


def _history_data() -> dict:
    return {
        "success": True,
        "label": "Big lamp",
        "attribute": "switch",
        "hoursBack": 24,
        "temporalAnalysis": {
            "attribute": "switch",
            "activeState": "on",
            "inactiveState": "off",
            "intervalCount": 5,
            "totalActiveSeconds": 16260,
            "totalActiveDuration": "4h 31m",
            "longestActiveSeconds": 9480,
            "longestActiveDuration": "2h 38m",
            "continuous": False,
            "coverage": "complete",
            "totalIsLowerBound": False,
        },
    }


class FakeMCP:
    async def call_tool(self, name, arguments):
        raise AssertionError("local history handler should not call the remote MCP")


@pytest.mark.asyncio
async def test_history_tool_receipt_exposes_temporal_proof() -> None:
    async def local_history(arguments):
        return MCPToolResult(
            "homebrain_device_history",
            arguments,
            {},
            "ok",
            _history_data(),
        )

    evidence = EvidenceRecorder()
    executor = ToolExecutor(
        FakeMCP(),
        evidence,
        local_handlers={"homebrain_device_history": local_history},
        clock=iter([1.0, 1.01]).__next__,
    )
    token = evidence.begin()
    try:
        execution = await executor.execute(
            "homebrain_device_history",
            {"name": "big lamp", "attribute": "switch", "hours_back": 24},
            tool=MCPTool(
                "homebrain_device_history",
                "Read bounded device history",
                {},
                annotations={"effect": ToolEffect.READ.value},
            ),
            evidence_kind="deterministic_device_event_history",
        )
        receipt = evidence.receipts()[0]
    finally:
        evidence.reset(token)

    assert execution.success is True
    assert receipt["summary"] == (
        "temporal history: intervals=5, total=4h 31m (16260s), "
        "longest=2h 38m, coverage=complete"
    )
    assert receipt["details"] == {
        "label": "Big lamp",
        "attribute": "switch",
        "hoursBack": 24,
        "timeWindow": None,
        "temporalAnalysis": {
            "activeState": "on",
            "inactiveState": "off",
            "totalActiveDuration": "4h 31m",
            "totalActiveSeconds": 16260,
            "intervalCount": 5,
            "longestActiveDuration": "2h 38m",
            "longestActiveSeconds": 9480,
            "continuous": False,
            "coverage": "complete",
            "totalIsLowerBound": False,
        },
    }


def _outcome(message: str) -> SimpleNamespace:
    return SimpleNamespace(
        route="unified-mcp-agent",
        request_class="live-read",
        message=message,
        choices=[],
        confirmation_required=False,
        confirmation_count=0,
        automation_items=[],
        evidence=[{
            "tool": "homebrain_device_history",
            "success": True,
            "details": {
                "label": "Big lamp",
                "attribute": "switch",
                "hoursBack": 24,
                "temporalAnalysis": _history_data()["temporalAnalysis"],
            },
        }],
        metrics={
            "outcome": "success",
            "counters": {"model_rounds": 2},
            "timings_ms": {},
        },
    )


def test_api_response_corrects_wrong_model_total_from_temporal_proof() -> None:
    response = build_agent_response(
        _outcome(
            "The big lamp was on for a total of 4 hours and 29 minutes last night, "
            "across 5 separate intervals. The longest stretch was 2 hours and 38 minutes."
        ),
        model="gemma4:31b",
        elapsed_ms=3900,
        version="0.10.450",
    )

    assert response["message"] == (
        "Big lamp was on for a total of 4h 31m across 5 separate intervals. "
        "The longest interval was 2h 38m."
    )
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_api_response_preserves_correct_model_total() -> None:
    original = (
        "Big lamp was on for a total of 4 hours and 31 minutes across 5 intervals. "
        "The longest interval was 2 hours and 38 minutes."
    )
    response = build_agent_response(
        _outcome(original),
        model="gemma4:31b",
        elapsed_ms=3900,
        version="0.10.450",
    )

    assert response["message"] == original
    assert "finalAnswerCorrectionApplied" not in response["evidence"][0]["details"]
