from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from history_temporal_analysis import history_temporal_evidence_details  # noqa: E402
from mcp_client import MCPTool, MCPToolResult  # noqa: E402
from tool_discovery_catalog import ToolDiscoveryCatalog  # noqa: E402


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
            "counters": {"model_rounds": 2},
            "timings_ms": {},
        }
    )


def _history_receipt(
    label: str = "Bedroom 3 Light",
    *,
    attribute: str = "switch",
    intervals: int = 5,
    active_state: str = "on",
    inactive_state: str = "off",
) -> dict[str, Any]:
    return {
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": label,
            "attribute": attribute,
            "historySourceIntegrity": "unverified",
            "historySourceIntegrityVerified": False,
            "temporalAnalysis": {
                "activeState": active_state,
                "inactiveState": inactive_state,
                "intervalCount": intervals,
                "totalActiveDuration": "1h 44m" if intervals else "0s",
                "totalActiveSeconds": 6237 if intervals else 0,
                "longestActiveDuration": "1h 27m" if intervals else "0s",
                "longestActiveSeconds": 5234 if intervals else 0,
                "coverage": "partial",
                "totalIsLowerBound": False,
                "durationReliability": "unverified-event-stream",
                "sourceIntegrity": "unverified",
                "sourceIntegrityVerified": False,
                "windowed": True,
                "windowLabel": "last night",
                "boundaryStateKnown": False,
            },
        },
    }


def test_temporal_evidence_details_include_bounded_interval_proof() -> None:
    result = {
        "label": "Bedroom 3 Light",
        "attribute": "switch",
        "hoursBack": 24,
        "temporalAnalysis": {
            "activeState": "on",
            "inactiveState": "off",
            "intervalCount": 2,
            "intervals": [
                {
                    "start": "2026-09-18T00:02:53+01:00",
                    "end": "2026-09-18T01:30:07+01:00",
                    "startNatural": "12:02 am",
                    "endNatural": "1:30 am",
                    "durationSeconds": 5234,
                    "duration": "1h 27m",
                    "clippedAtWindowStart": False,
                    "clippedAtWindowEnd": False,
                },
                {
                    "start": "2026-09-18T01:32:51+01:00",
                    "end": "2026-09-18T01:45:02+01:00",
                    "durationSeconds": 731,
                    "duration": "12m",
                },
            ],
            "totalActiveSeconds": 5965,
            "totalActiveDuration": "1h 39m",
            "coverage": "partial",
            "sourceIntegrityVerified": False,
            "durationReliability": "unverified-event-stream",
        },
    }

    details = history_temporal_evidence_details(result)
    assert details is not None
    temporal = details["temporalAnalysis"]
    assert temporal["observedIntervals"][0]["durationSeconds"] == 5234
    assert temporal["observedIntervals"][1]["start"].startswith("2026-09-18T01:32:51")
    assert temporal["observedIntervalsTruncated"] is False


def test_interval_cardinality_guard_corrects_exhaustive_two_period_claim() -> None:
    response = build_agent_response(
        FakeOutcome(
            message=(
                "Bedroom 3 Light was on during two separate periods last night. "
                "The Late Night mode change is only a correlation."
            ),
            evidence=[_history_receipt()],
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )

    assert "5 observed bounded on intervals" in response["message"]
    assert "two separate periods" not in response["message"]
    assert response["message"].endswith(
        "The Late Night mode change is only a correlation."
    )
    assert response["evidence"][0]["details"]["finalAnswerCorrectionApplied"] is True


def test_interval_cardinality_guard_allows_nonexhaustive_longest_subset() -> None:
    message = (
        "The two longest periods were 00:02-01:30 and 01:32-01:45. "
        "There were five observed intervals in total."
    )
    response = build_agent_response(
        FakeOutcome(message=message, evidence=[_history_receipt()]),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )
    assert response["message"] == message


def test_unverified_zero_motion_data_claim_is_rewritten_without_erasing_subject_history() -> None:
    response = build_agent_response(
        FakeOutcome(
            message=(
                "Bedroom 3 Light has several recorded intervals. "
                "There is no recorded motion data for the Bedroom 3 sensors."
            ),
            evidence=[
                _history_receipt(),
                _history_receipt(
                    "Bedroom 3 Soft Sensor",
                    attribute="motion",
                    intervals=0,
                    active_state="active",
                    inactive_state="inactive",
                ),
            ],
        ),
        model="gemma4:31b",
        elapsed_ms=10,
        version="0.10.463",
    )

    assert response["message"].startswith(
        "Bedroom 3 Light has several recorded intervals."
    )
    assert "No bounded active interval was established for Bedroom 3 Soft Sensor" in response["message"]
    assert "does not prove it stayed inactive" in response["message"]
    assert "no recorded motion data" not in response["message"].casefold()


def _tool(name: str, description: str, schema: dict[str, Any] | None = None) -> MCPTool:
    return MCPTool(name, description, schema or {"type": "object"})


def test_gateway_operation_guard_rejects_operation_not_listed_by_gateway() -> None:
    diagnostics = _tool(
        "hub_read_diagnostics",
        "Read diagnostics via hub_get_logs, hub_get_jobs, hub_get_performance_stats.",
    )
    catalog = ToolDiscoveryCatalog([diagnostics])

    error = catalog.gateway_operation_error(
        "hub_read_diagnostics",
        {"tool": "hub_list_apps", "args": {"scope": "instances"}},
    )

    assert error is not None
    assert "hub_list_apps" in error
    assert "not listed" in error


def test_gateway_operation_guard_uses_live_discovery_mapping() -> None:
    diagnostics = _tool(
        "hub_read_diagnostics",
        "Read diagnostics via hub_get_logs, hub_get_jobs.",
    )
    apps = _tool(
        "hub_read_apps_code",
        "Read installed apps via hub_list_apps, hub_get_app_config.",
    )
    search = _tool("hub_search_tools", "search")
    catalog = ToolDiscoveryCatalog([search, diagnostics, apps])
    catalog.expand(
        MCPToolResult(
            "hub_search_tools",
            {},
            {},
            "",
            {
                "results": [
                    {"tool": "hub_list_apps", "gateway": "hub_read_apps_code"}
                ]
            },
        )
    )

    error = catalog.gateway_operation_error(
        "hub_read_diagnostics",
        {"tool": "hub_list_apps"},
    )
    assert error is not None
    assert "hub_read_apps_code" in error
