from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from evidence_recorder import EvidenceRecorder  # noqa: E402
from history_temporal_analysis import history_temporal_evidence_details  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_registry import ToolEffect  # noqa: E402


def _interval(start: str, end: str, duration: str, seconds: int) -> dict[str, Any]:
    return {
        "start": start,
        "end": end,
        "startNatural": start,
        "endNatural": end,
        "duration": duration,
        "durationSeconds": seconds,
        "clippedAtWindowStart": False,
        "clippedAtWindowEnd": False,
    }


def _light_temporal() -> dict[str, Any]:
    intervals = [
        _interval("2026-09-17T23:55:42+01:00", "2026-09-17T23:59:18+01:00", "4m", 216),
        _interval("2026-09-17T23:59:30+01:00", "2026-09-18T00:00:21+01:00", "51s", 51),
        _interval("2026-09-18T00:02:53+01:00", "2026-09-18T01:30:07+01:00", "1h 27m", 5234),
        _interval("2026-09-18T01:32:51+01:00", "2026-09-18T01:45:02+01:00", "12m", 731),
        _interval("2026-09-18T01:45:10+01:00", "2026-09-18T01:45:15+01:00", "5s", 5),
    ]
    return {
        "activeState": "on",
        "inactiveState": "off",
        "intervalCount": 5,
        "intervals": intervals,
        "totalActiveDuration": "1h 44m",
        "totalActiveSeconds": 6237,
        "longestActiveDuration": "1h 27m",
        "longestActiveSeconds": 5234,
        "continuous": False,
        "coverage": "partial",
        "totalIsLowerBound": False,
        "windowed": True,
        "windowLabel": "last night",
        "sourceIntegrity": "unverified",
        "sourceIntegrityVerified": False,
        "durationReliability": "unverified-event-stream",
        "observedBoundedIntervalsOnly": True,
    }


def _history_receipt(
    label: str,
    *,
    attribute: str | None,
    temporal: dict[str, Any] | None = None,
    observed: list[str] | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "label": label,
        "attribute": attribute,
        "hoursBack": 24,
    }
    if temporal is not None:
        details["temporalAnalysis"] = temporal
    if observed is not None:
        details["observedEventNames"] = observed
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "evidence_kind": "deterministic_device_event_history",
        "arguments": {"name": label, **({"attribute": attribute} if attribute else {})},
        "summary": "history",
        "details": details,
    }


@dataclass
class FakeOutcome:
    message: str
    evidence: list[dict[str, Any]]
    request_class: str = "live-read"
    choices: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_count: int = 0
    automation_items: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "outcome": "success",
            "counters": {"model_rounds": 4},
            "timings_ms": {},
        }
    )


def test_history_evidence_exposes_bounded_interval_proof() -> None:
    data = {
        "success": True,
        "label": "Bedroom 3 Light",
        "deviceId": "7841",
        "attribute": "switch",
        "hoursBack": 24,
        "events": [
            {"name": "switch", "value": "off"},
            {"name": "level", "value": 15},
        ],
        "temporalAnalysis": _light_temporal(),
    }

    details = history_temporal_evidence_details(data)

    assert details is not None
    temporal = details["temporalAnalysis"]
    assert temporal["intervalCount"] == 5
    assert len(temporal["boundedIntervals"]) == 5
    assert temporal["boundedIntervals"][2]["duration"] == "1h 27m"
    assert temporal["boundedIntervalsTruncated"] is False
    assert details["observedEventNames"] == ["switch", "level"]


def test_generic_history_evidence_exposes_observed_event_names_without_fake_temporal_summary() -> None:
    details = history_temporal_evidence_details(
        {
            "success": True,
            "label": "Bedroom 3 Sensor T1",
            "deviceId": "7745",
            "attribute": None,
            "hoursBack": 24,
            "events": [
                {"name": "temperature", "value": 21.5},
                {"name": "illuminance", "value": 124},
                {"name": "temperature", "value": 21.6},
            ],
        }
    )

    assert details is not None
    assert details["attribute"] is None
    assert details["observedEventNames"] == ["temperature", "illuminance"]
    assert "temporalAnalysis" not in details


def test_interval_cardinality_guard_turns_two_periods_into_subset_of_five() -> None:
    message = (
        "The Bedroom 3 Light was on during two separate periods last night:\n"
        "* 00:02 to 01:30.\n"
        "* 01:32 to 01:45.\n"
        "The specific trigger remains unproven."
    )
    evidence = [
        _history_receipt("Bedroom 3 Light", attribute="switch", temporal=_light_temporal()),
        _history_receipt(
            "Bedroom 3 Soft Sensor",
            attribute="motion",
            temporal={
                "activeState": "active",
                "inactiveState": "inactive",
                "intervalCount": 0,
                "totalActiveDuration": "0s",
                "totalActiveSeconds": 0,
                "coverage": "partial",
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "durationReliability": "unverified-event-stream",
                "windowLabel": "last night",
            },
        ),
    ]

    response = build_agent_response(
        FakeOutcome(message=message, evidence=evidence),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )

    assert "during 2 highlighted periods out of 5 observed bounded on intervals" in response["message"]
    assert "* 00:02 to 01:30." in response["message"]
    assert "* 01:32 to 01:45." in response["message"]
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_attribute_absence_guard_requires_explicit_illuminance_analysis() -> None:
    motion_zero = {
        "activeState": "active",
        "inactiveState": "inactive",
        "intervalCount": 0,
        "totalActiveDuration": "0s",
        "totalActiveSeconds": 0,
        "coverage": "partial",
        "sourceIntegrity": "unverified",
        "sourceIntegrityVerified": False,
        "durationReliability": "unverified-event-stream",
        "windowLabel": "last night",
    }
    evidence = [
        _history_receipt("Bedroom 3 Light", attribute="switch", temporal=_light_temporal()),
        _history_receipt("Bedroom 3 Soft Sensor", attribute="motion", temporal=motion_zero),
        _history_receipt(
            "Bedroom 3 Sensor T1",
            attribute=None,
            observed=["temperature", "illuminance"],
        ),
    ]
    response = build_agent_response(
        FakeOutcome(
            message=(
                "There is no recorded motion or illuminance data for the Bedroom 3 "
                "sensors during these specific windows to correlate with the light."
            ),
            evidence=evidence,
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )

    assert "no recorded motion or illuminance data" not in response["message"].casefold()
    assert "no bounded active interval was established" in response["message"].casefold()
    assert "contains recorded illuminance rows" in response["message"].casefold()
    assert "illuminance was not explicitly analyzed" in response["message"].casefold()


class FakeMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        self.calls.append((name, arguments))
        return MCPToolResult(name, arguments, {}, "unexpected", {"success": True})


@pytest.mark.asyncio
async def test_invalid_gateway_subtool_is_rejected_before_remote_execution() -> None:
    mcp = FakeMCP()
    evidence = EvidenceRecorder()
    metrics = RequestMetrics()
    metric_token = metrics.begin()
    evidence_token = evidence.begin()
    try:
        executor = ToolExecutor(mcp, evidence)
        tool = MCPTool(
            "hub_read_diagnostics",
            "Diagnostics gateway",
            {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": ["hub_get_logs", "hub_get_jobs"],
                    },
                    "args": {"type": "object"},
                },
            },
            annotations={"effect": ToolEffect.READ.value},
        )
        execution = await executor.execute(
            "hub_read_diagnostics",
            {"tool": "hub_list_apps", "args": {"scope": "instances"}},
            tool=tool,
        )
        receipts = evidence.receipts()
        metric_snapshot = metrics.snapshot()
    finally:
        evidence.reset(evidence_token)
        metrics.reset(metric_token)

    assert execution.success is False
    assert mcp.calls == []
    payload = json.loads(execution.content)
    assert "Invalid sub-tool 'hub_list_apps'" in payload["error"]
    assert "No MCP command was sent" in payload["host_instruction"]
    assert receipts[0]["success"] is False
    assert metric_snapshot["counters"]["tool_schema_rejections"] == 1
