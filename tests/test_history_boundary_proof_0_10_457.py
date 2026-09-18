from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_history_service import DeviceHistoryService  # noqa: E402
from history_result_enrichment import enrich_history_result  # noqa: E402
from history_temporal_analysis import (  # noqa: E402
    analyze_state_intervals_in_window,
    history_temporal_evidence_details,
)
from history_time_windows import (  # noqa: E402
    parse_history_window_request,
    reset_history_window_request,
    set_history_window_request,
)
from mcp_client import MCPToolResult  # noqa: E402


START = datetime.fromisoformat("2026-09-17T18:00:00+01:00")
END = datetime.fromisoformat("2026-09-18T08:00:00+01:00")


def _event(value: str, timestamp: str, *, state_change: Any = "__missing__") -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": "switch",
        "value": value,
        "date": timestamp,
    }
    if state_change != "__missing__":
        row["isStateChange"] = state_change
    return row


def _history_result(data: dict[str, Any]) -> MCPToolResult:
    return MCPToolResult(
        "homebrain_device_history",
        {"name": data.get("label", "device")},
        {},
        "",
        data,
    )


def test_unmarked_first_state_report_cannot_infer_whole_window_boundary() -> None:
    # This is the dangerous 0.10.456 shape: an ordinary early "off" report
    # used to be treated as a transition, which inverted the preceding state
    # and could manufacture almost a full night's "on" duration.
    events = [
        _event("off", "2026-09-18T07:55:00+01:00", state_change=True),
        _event("on", "2026-09-18T07:54:00+01:00", state_change=True),
        _event("off", "2026-09-18T07:50:00+01:00", state_change=True),
        _event("on", "2026-09-18T07:47:00+01:00", state_change=True),
        _event("off", "2026-09-18T07:39:00+01:00"),
    ]

    temporal = analyze_state_intervals_in_window(
        "switch",
        events,
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
        window_ongoing=False,
    )

    assert temporal is not None
    assert temporal["boundaryStateKnown"] is False
    assert temporal["boundaryBasis"] == "source-integrity-unverified"
    assert temporal["coverage"] == "partial"
    assert temporal["totalIsLowerBound"] is False
    assert temporal["sourceIntegrityVerified"] is False
    assert temporal["durationReliability"] == "unverified-event-stream"
    # Only the observed on periods after a known row may contribute.
    assert temporal["totalActiveSeconds"] == 240
    assert temporal["longestActiveSeconds"] == 180
    assert temporal["analyzedStateEventCount"] == 5
    assert temporal["firstWindowStateEvent"]["state"] == "off"
    assert temporal["firstWindowStateEvent"]["isStateChange"] is None


def test_explicit_transition_is_diagnostic_but_not_exact_without_integrity() -> None:
    events = [
        _event("off", "2026-09-18T07:55:00+01:00", state_change=True),
        _event("on", "2026-09-18T07:54:00+01:00", state_change=True),
        _event("off", "2026-09-18T07:39:00+01:00", state_change="true"),
    ]

    temporal = analyze_state_intervals_in_window(
        "switch",
        events,
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
    )

    assert temporal is not None
    assert temporal["boundaryStateKnown"] is False
    assert temporal["boundaryBasis"] == "first-transition-inference-untrusted"
    assert temporal["inferredBoundaryState"] == "on"
    assert temporal["coverage"] == "partial"
    assert temporal["sourceIntegrityVerified"] is False
    assert temporal["firstWindowStateEvent"]["isStateChange"] == "true"


def test_verified_event_stream_can_use_first_transition_boundary() -> None:
    events = [
        _event("off", "2026-09-18T07:55:00+01:00", state_change=True),
        _event("on", "2026-09-18T07:54:00+01:00", state_change=True),
        _event("off", "2026-09-18T07:39:00+01:00", state_change="true"),
    ]

    temporal = analyze_state_intervals_in_window(
        "switch",
        events,
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
        source_integrity_verified=True,
    )

    assert temporal is not None
    assert temporal["boundaryStateKnown"] is True
    assert temporal["boundaryBasis"] == "first-transition-inference"
    assert temporal["coverage"] == "complete"
    assert temporal["durationReliability"] == "exact"


def test_unmarked_post_window_report_cannot_close_unknown_zero() -> None:
    data = {
        "success": True,
        "label": "Hallway Light 1",
        "attribute": "switch",
        "sourceEventCount": 1,
        "analysisEventCount": 1,
        "events": [
            _event("on", "2026-09-18T09:00:00+01:00"),
        ],
        "timeWindow": {
            "kind": "last_night",
            "label": "last night",
            "start": START.isoformat(),
            "end": END.isoformat(),
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
            "windowStart": START.isoformat(),
            "windowEnd": END.isoformat(),
            "windowOngoing": False,
            "boundaryStateKnown": False,
            "boundaryBasis": "unknown",
            "sourceCompleteToWindowStart": True,
        },
    }

    enriched = enrich_history_result("homebrain_device_history", _history_result(data))
    temporal = enriched.data["temporalAnalysis"]

    assert temporal["coverage"] == "partial"
    assert temporal["totalIsLowerBound"] is True
    assert temporal["boundaryStateKnown"] is False
    assert temporal["boundaryBasis"] == "unknown"


def test_explicit_and_inferred_mixed_history_share_the_same_temporal_result() -> None:
    mixed_events = [
        {"name": "level", "value": "45", "date": "2026-09-18T07:15:00+01:00"},
        _event("off", "2026-09-18T07:55:00+01:00", state_change=True),
        _event("on", "2026-09-18T07:54:00+01:00", state_change=True),
        {"name": "level", "value": "30", "date": "2026-09-18T06:59:00+01:00"},
        _event("off", "2026-09-18T07:50:00+01:00", state_change=True),
        _event("on", "2026-09-18T07:47:00+01:00", state_change=True),
        _event("on", "2026-09-18T07:39:00+01:00", state_change=True),
    ]
    base = {
        "success": True,
        "label": "Hallway Light 1",
        "sourceEventCount": len(mixed_events),
        "events": mixed_events,
        "timeWindow": {
            "kind": "last_night",
            "label": "last night",
            "start": START.isoformat(),
            "end": END.isoformat(),
            "ongoing": False,
            "sourceCompleteToStart": True,
        },
    }

    direct = analyze_state_intervals_in_window(
        "switch",
        [row for row in mixed_events if row.get("name") == "switch"],
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
    )
    inferred_result = enrich_history_result(
        "homebrain_device_history",
        _history_result({**base, "attribute": None, "analysisEventCount": len(mixed_events)}),
    )
    inferred = inferred_result.data["temporalAnalysis"]

    assert inferred_result.data["attribute"] == "switch"
    assert inferred_result.data["attributeInferred"] is True
    assert inferred["totalActiveSeconds"] == direct["totalActiveSeconds"]
    assert inferred["intervalCount"] == direct["intervalCount"]
    assert inferred["coverage"] == direct["coverage"]


def test_evidence_details_expose_inference_and_event_counts() -> None:
    result_data = {
        "label": "Hallway Light 1",
        "attribute": "switch",
        "attributeInferred": True,
        "hoursBack": 24,
        "sourceEventCount": 29,
        "analysisEventCount": 12,
        "timeWindow": {"label": "last night"},
        "temporalAnalysis": {
            "activeState": "on",
            "inactiveState": "off",
            "totalActiveDuration": "8m",
            "totalActiveSeconds": 505,
            "intervalCount": 6,
            "longestActiveDuration": "3m",
            "longestActiveSeconds": 183,
            "coverage": "complete",
            "totalIsLowerBound": False,
            "windowed": True,
            "boundaryStateKnown": True,
            "boundaryBasis": "first-transition-inference",
            "sourceCompleteToWindowStart": True,
            "analyzedStateEventCount": 12,
            "firstWindowStateEvent": {
                "timestamp": "2026-09-18T07:39:00+01:00",
                "state": "on",
                "isStateChange": True,
            },
            "predecessorStateEvent": None,
        },
    }

    details = history_temporal_evidence_details(result_data)

    assert details is not None
    assert details["attributeInferred"] is True
    assert details["sourceEventCount"] == 29
    assert details["analysisEventCount"] == 12
    assert details["temporalAnalysis"]["analyzedStateEventCount"] == 12
    assert details["temporalAnalysis"]["firstWindowStateEvent"]["state"] == "on"


class AmbiguousHistoryMCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        self.calls.append((name, arguments))
        if name == "hub_get_info":
            raise AssertionError("timezone must not be read before target resolution")
        if name == "hub_read_devices" and arguments.get("tool") == "hub_list_devices":
            return MCPToolResult(
                name,
                arguments,
                {},
                "ok",
                {
                    "devices": [
                        {"id": "1", "label": "Hallway Light 1", "capabilities": ["Switch"]},
                        {"id": "2", "label": "Hallway Light 2", "capabilities": ["Switch"]},
                    ]
                },
            )
        raise AssertionError((name, arguments))


@pytest.mark.asyncio
async def test_ambiguous_semantic_history_skips_timezone_read() -> None:
    mcp = AmbiguousHistoryMCP()
    service = DeviceHistoryService(mcp, lambda *args, **kwargs: None)
    token = set_history_window_request(
        parse_history_window_request("How long was hallway light on last night?")
    )
    try:
        result = await service.history({"name": "hallway light", "attribute": "switch"})
    finally:
        reset_history_window_request(token)

    assert result.is_error is True
    assert result.data["error"] == "device is ambiguous"
    assert result.data["alternatives"] == ["Hallway Light 1", "Hallway Light 2"]
    assert all(name != "hub_get_info" for name, _arguments in mcp.calls)
