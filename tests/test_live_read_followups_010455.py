from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from datetime import datetime


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from aggregate_fallback_policy import (  # noqa: E402
    blocked_generic_fallback,
    observe_aggregate_result,
    reset_aggregate_fallback_policy,
)
from api_response_builder import build_agent_response  # noqa: E402
from deterministic_tool_presenter import present_tool_result  # noqa: E402
from history_time_windows import parse_history_window_request, resolve_history_window  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402
from request_metrics import RequestMetrics  # noqa: E402
from webui import render_page  # noqa: E402


def test_during_the_night_uses_the_same_auditable_window_as_last_night() -> None:
    parsed = parse_history_window_request("Why was the hallway light on during the night?")
    assert parsed == {"kind": "last_night", "label": "last night"}

    window = resolve_history_window(
        parsed,
        now=datetime(2026, 9, 17, 22, 0, tzinfo=ZoneInfo("Europe/London")),
    )
    assert window is not None
    assert window.start.isoformat() == "2026-09-16T18:00:00+01:00"
    assert window.end.isoformat() == "2026-09-17T08:00:00+01:00"


def test_history_ambiguity_uses_or_so_two_choices_remain_separate() -> None:
    message = present_tool_result(
        "homebrain_device_history",
        {
            "success": False,
            "requested": "hallway light",
            "alternatives": ["Hallway Light 1", "Hallway Light 2"],
        },
        failed=True,
    )
    assert message == (
        "I could not resolve **hallway light** uniquely. Possible matches: "
        "Hallway Light 1 or Hallway Light 2."
    )


def test_api_boundary_corrects_named_no_history_claim_contradicted_by_proof() -> None:
    outcome = SimpleNamespace(
        route="unified-mcp-agent",
        request_class="live-read",
        message=(
            "Hallway Light 1 was on for 7 minutes. "
            "I have no recorded data for Hallway Light 2 during this period."
        ),
        choices=[],
        confirmation_required=False,
        confirmation_count=0,
        automation_items=[],
        metrics={"outcome": "success", "counters": {"model_rounds": 3}, "timings_ms": {}},
        evidence=[
            {
                "tool": "homebrain_device_history",
                "success": True,
                "details": {
                    "label": "Hallway Light 1",
                    "attribute": "switch",
                    "temporalAnalysis": {
                        "intervalCount": 6,
                        "totalActiveDuration": "7m",
                        "totalActiveSeconds": 445,
                        "totalIsLowerBound": False,
                    },
                },
            },
            {
                "tool": "homebrain_device_history",
                "success": True,
                "details": {
                    "label": "Hallway Light 2",
                    "attribute": "switch",
                    "temporalAnalysis": {
                        "intervalCount": 6,
                        "totalActiveDuration": "7m",
                        "totalActiveSeconds": 445,
                        "totalIsLowerBound": False,
                    },
                },
            },
        ],
    )

    response = build_agent_response(outcome, model="gemma4:31b", elapsed_ms=100, version="0.10.455")
    assert "no recorded data for Hallway Light 2" not in response["message"]
    assert "Hallway Light 2 has recorded history in this evidence" in response["message"]
    assert response["evidence"][1]["details"]["finalAnswerCorrectionApplied"] is True


def test_complete_nonempty_power_result_blocks_generic_value_fallback() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        reset_aggregate_fallback_policy()
        observe_aggregate_result(
            "homebrain_query_devices",
            {"attribute": "power", "operation": "top"},
            MCPToolResult(
                "homebrain_query_devices",
                {"attribute": "power", "operation": "top"},
                {},
                "ok",
                {"complete": True, "count": 4, "results": [{"label": "A", "value": 50}]},
            ),
        )
        reason = blocked_generic_fallback(
            "homebrain_query_devices",
            {"attribute": "value", "operation": "top"},
        )
        assert reason is not None
        assert "complete, non-empty canonical aggregate" in reason
    finally:
        metrics.reset(token)


def test_empty_power_result_still_allows_generic_value_fallback() -> None:
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        reset_aggregate_fallback_policy()
        observe_aggregate_result(
            "homebrain_query_devices",
            {"attribute": "power", "operation": "top"},
            MCPToolResult(
                "homebrain_query_devices",
                {"attribute": "power", "operation": "top"},
                {},
                "ok",
                {"complete": True, "count": 0, "results": []},
            ),
        )
        assert blocked_generic_fallback(
            "homebrain_query_devices",
            {"attribute": "valueStr", "operation": "top"},
        ) is None
    finally:
        metrics.reset(token)


def test_webui_choice_keeps_original_history_question_for_semantic_window() -> None:
    page = render_page("HomeBrain", "0.10.455")
    assert "Device clarification: use exactly ${choice}." in page
    assert "const original=String(question||'').trim()" in page
