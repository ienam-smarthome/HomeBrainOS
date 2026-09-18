from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from history_result_enrichment import enrich_history_result  # noqa: E402
from history_temporal_analysis import analyze_state_intervals_in_window  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


START = datetime.fromisoformat("2026-09-17T18:00:00+01:00")
END = datetime.fromisoformat("2026-09-18T08:00:00+01:00")


def _event(value: str, timestamp: str, *, state_change: Any = True) -> dict[str, Any]:
    return {
        "name": "switch",
        "value": value,
        "date": timestamp,
        "isStateChange": state_change,
    }


def _result(data: dict[str, Any]) -> MCPToolResult:
    return MCPToolResult(
        "homebrain_device_history",
        {"name": data.get("label", "device")},
        {},
        "",
        data,
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


def _unverified_receipt(
    *,
    total: str = "8m",
    seconds: int = 505,
    intervals: int = 6,
) -> dict[str, Any]:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Hallway Light 1",
            "attribute": "switch",
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "temporalAnalysis": {
                "activeState": "on",
                "inactiveState": "off",
                "totalActiveDuration": total,
                "totalActiveSeconds": seconds,
                "intervalCount": intervals,
                "longestActiveDuration": "3m",
                "longestActiveSeconds": 183,
                "coverage": "partial",
                "totalIsLowerBound": False,
                "durationReliability": "unverified-event-stream",
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "windowed": True,
                "windowLabel": "last night",
                "boundaryStateKnown": False,
                "boundaryBasis": "source-integrity-unverified",
            },
        },
    }


def test_page_complete_is_not_event_stream_complete() -> None:
    temporal = analyze_state_intervals_in_window(
        "switch",
        [
            _event("on", "2026-09-18T07:39:00+01:00"),
            _event("off", "2026-09-18T07:42:00+01:00"),
            _event("on", "2026-09-18T07:47:00+01:00"),
            _event("off", "2026-09-18T07:50:00+01:00"),
        ],
        start=START,
        end=END,
        window_label="last night",
        source_complete_to_start=True,
    )

    assert temporal is not None
    assert temporal["pageCompleteToWindowStart"] is True
    assert temporal["sourceCompleteToWindowStart"] is True
    assert temporal["sourceIntegrityVerified"] is False
    assert temporal["sourceIntegrity"] == "unverified"
    assert temporal["durationReliability"] == "unverified-event-stream"
    assert temporal["coverage"] == "partial"
    assert temporal["continuous"] is False
    # Missing transitions can make a paired duration either too high or too low,
    # so the estimate must not be mislabeled as a mathematical lower bound.
    assert temporal["totalIsLowerBound"] is False


def test_post_window_transition_never_creates_synthetic_whole_night_interval() -> None:
    data = {
        "success": True,
        "label": "Hallway Light 1",
        "attribute": "switch",
        "historySourceIntegrity": "unverified",
        "historySourceIntegrityVerified": False,
        "analysisEventCount": 1,
        "sourceEventCount": 12,
        "events": [
            _event("on", "2026-09-18T09:22:14+01:00"),
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
            "totalIsLowerBound": False,
            "durationReliability": "unverified-event-stream",
            "sourceIntegrity": "unverified",
            "sourceIntegrityVerified": False,
            "windowed": True,
            "windowLabel": "last night",
            "windowStart": START.isoformat(),
            "windowEnd": END.isoformat(),
            "windowOngoing": False,
            "boundaryStateKnown": False,
            "boundaryBasis": "source-integrity-unverified",
            "sourceCompleteToWindowStart": True,
        },
    }

    enriched = enrich_history_result("homebrain_device_history", _result(data))
    temporal = enriched.data["temporalAnalysis"]

    assert temporal["intervalCount"] == 0
    assert temporal["totalActiveSeconds"] == 0
    assert temporal["boundaryStateKnown"] is False
    assert "postWindowStateEvidence" not in temporal
    assert temporal.get("predecessorStateEvent") is None


def test_unverified_exact_duration_claim_is_rewritten_as_estimate() -> None:
    outcome = FakeOutcome(
        message=(
            "Hallway Light 1 was on for a total of 8 minutes last night "
            "across 6 intervals."
        ),
        evidence=[_unverified_receipt()],
    )

    response = build_agent_response(
        outcome,
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.458",
    )

    assert "estimate of 8m" in response["message"]
    assert "not an exact total or a mathematical lower bound" in response["message"]
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_unverified_continuity_claim_is_rewritten() -> None:
    outcome = FakeOutcome(
        message=(
            "Hallway Light 1 was on continuously throughout the night. "
            "It remained on until 9:22 AM."
        ),
        evidence=[_unverified_receipt(total="0s", seconds=0, intervals=0)],
    )

    response = build_agent_response(
        outcome,
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.458",
    )

    assert "No bounded on interval was established" in response["message"]
    assert "does not prove it stayed off" in response["message"]
    assert "continuously throughout" not in response["message"]


def test_unverified_absence_claim_is_rewritten() -> None:
    outcome = FakeOutcome(
        message="Hallway Light 1 was not on last night.",
        evidence=[_unverified_receipt(total="0s", seconds=0, intervals=0)],
    )

    response = build_agent_response(
        outcome,
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.458",
    )

    assert "No bounded on interval was established" in response["message"]
    assert "event stream has not been independently verified as complete" in response["message"]
    assert "does not prove it stayed off" in response["message"]
