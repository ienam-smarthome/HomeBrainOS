from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from history_result_enrichment import (  # noqa: E402
    enrich_history_result,
    prepare_history_arguments,
)
from history_time_windows import (  # noqa: E402
    reset_history_window_request,
    set_history_window_request,
)
from mcp_client import MCPToolResult  # noqa: E402
from reasoning_policy import (  # noqa: E402
    blocked_selected_target,
    prepare_reasoning_turn,
    selected_reasoning_target,
)


@dataclass
class FakeOutcome:
    message: str
    evidence: list[dict[str, Any]]
    request_class: str = "live-read"
    choices: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    confirmation_count: int = 0
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "outcome": "success",
            "counters": {"model_rounds": 2, "tool_calls": 1},
            "timings_ms": {"total": 10},
        }
    )


def _history_result(data: dict[str, Any]) -> MCPToolResult:
    return MCPToolResult(
        "homebrain_device_history",
        {"name": data.get("label", "device")},
        {},
        "",
        data,
    )


def test_semantic_attribute_less_history_uses_full_bounded_page() -> None:
    token = set_history_window_request({"kind": "last_night", "label": "last night"})
    try:
        prepared = prepare_history_arguments(
            "homebrain_device_history", {"name": "Fan Switch (Tuya Local)"}
        )
    finally:
        reset_history_window_request(token)

    assert prepared["limit"] == 50


def test_attribute_less_semantic_history_infers_one_binary_attribute() -> None:
    data = {
        "success": True,
        "label": "Fan Switch (Tuya Local)",
        "attribute": None,
        "analysisEventCount": 4,
        "events": [
            {"name": "switch", "value": "off", "date": "2026-09-17T05:29:00+01:00", "isStateChange": True},
            {"name": "switch", "value": "on", "date": "2026-09-17T03:59:00+01:00", "isStateChange": True},
            {"name": "switch", "value": "off", "date": "2026-09-16T22:29:00+01:00", "isStateChange": True},
            {"name": "switch", "value": "on", "date": "2026-09-16T21:59:00+01:00", "isStateChange": True},
        ],
        "timeWindow": {
            "kind": "last_night",
            "label": "last night",
            "start": "2026-09-16T18:00:00+01:00",
            "end": "2026-09-17T08:00:00+01:00",
            "ongoing": False,
            "sourceCompleteToStart": True,
        },
    }

    enriched = enrich_history_result("homebrain_device_history", _history_result(data))
    temporal = enriched.data["temporalAnalysis"]

    assert enriched.data["attribute"] == "switch"
    assert enriched.data["attributeInferred"] is True
    assert temporal["intervalCount"] == 2
    assert temporal["totalActiveSeconds"] == 7200
    assert temporal["coverage"] == "complete"
    assert temporal["totalIsLowerBound"] is False


def test_first_transition_after_empty_window_can_prove_complete_zero() -> None:
    data = {
        "success": True,
        "label": "Hallway Light 1",
        "attribute": "switch",
        "analysisEventCount": 1,
        "events": [
            {
                "name": "switch",
                "value": "on",
                "date": "2026-09-17T22:43:00+01:00",
                "isStateChange": True,
            }
        ],
        "timeWindow": {
            "kind": "last_night",
            "label": "last night",
            "start": "2026-09-16T18:00:00+01:00",
            "end": "2026-09-17T08:00:00+01:00",
            "ongoing": False,
            "sourceCompleteToStart": True,
        },
        "temporalAnalysis": {
            "attribute": "switch",
            "activeState": "on",
            "inactiveState": "off",
            "intervalCount": 0,
            "intervals": [],
            "totalActiveSeconds": 0,
            "totalActiveDuration": "0s",
            "longestActiveSeconds": 0,
            "longestActiveDuration": "0s",
            "coverage": "partial",
            "totalIsLowerBound": True,
            "windowed": True,
            "windowLabel": "last night",
            "windowStart": "2026-09-16T18:00:00+01:00",
            "windowEnd": "2026-09-17T08:00:00+01:00",
            "windowOngoing": False,
            "boundaryStateKnown": False,
            "boundaryBasis": "unknown",
            "sourceCompleteToWindowStart": True,
        },
    }

    enriched = enrich_history_result("homebrain_device_history", _history_result(data))
    temporal = enriched.data["temporalAnalysis"]

    assert temporal["intervalCount"] == 0
    assert temporal["totalActiveSeconds"] == 0
    assert temporal["coverage"] == "complete"
    assert temporal["totalIsLowerBound"] is False
    assert temporal["boundaryStateKnown"] is True
    assert temporal["boundaryBasis"] == "first-transition-after-window-inference"
    assert temporal["postWindowStateEvidence"]["inferredWindowState"] == "off"


def test_partial_zero_history_cannot_be_serialized_as_proven_off() -> None:
    evidence = [
        {
            "tool": "homebrain_device_history",
            "success": True,
            "details": {
                "label": "Hallway Light 1",
                "attribute": "switch",
                "temporalAnalysis": {
                    "activeState": "on",
                    "inactiveState": "off",
                    "intervalCount": 0,
                    "totalActiveDuration": "0s",
                    "totalActiveSeconds": 0,
                    "coverage": "partial",
                    "totalIsLowerBound": True,
                    "windowed": True,
                    "windowLabel": "last night",
                    "boundaryStateKnown": False,
                },
            },
        }
    ]
    outcome = FakeOutcome(
        message="Hallway Light 1 was not on during last night.",
        evidence=evidence,
    )

    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=10, version="0.10.456"
    )

    assert "does not prove it stayed off" in response["message"]
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_explicit_clarification_binds_named_history_reads() -> None:
    messages = [
        {"role": "system", "content": "system"},
        {
            "role": "user",
            "content": (
                "Was the bathroom fan behaving normally last night?\n"
                "Device clarification: use exactly Fan Switch (Tuya Local)."
            ),
        },
    ]
    prepared, _tools = prepare_reasoning_turn(
        messages,
        [{"type": "function", "function": {"name": "homebrain_device_history"}}],
    )

    assert selected_reasoning_target() == "Fan Switch (Tuya Local)"
    assert blocked_selected_target(
        "homebrain_device_history", {"name": "Fan Boost"}
    ) is not None
    assert blocked_selected_target(
        "homebrain_device_history", {"name": "Fan Switch (Tuya Local)"}
    ) is None
    assert "BOUND DEVICE CLARIFICATION" in prepared[0]["content"]


def test_new_request_without_marker_clears_selected_target() -> None:
    prepare_reasoning_turn(
        [{"role": "user", "content": "Use this\nDevice clarification: use exactly Fan Switch."}],
        [{"type": "function", "function": {"name": "homebrain_device_history"}}],
    )
    assert selected_reasoning_target() == "Fan Switch"

    prepare_reasoning_turn(
        [{"role": "user", "content": "What is the hallway temperature?"}],
        [{"type": "function", "function": {"name": "homebrain_device_history"}}],
    )
    assert selected_reasoning_target() is None
