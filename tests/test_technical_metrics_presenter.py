from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from technical_metrics_presenter import present_request_metrics  # noqa: E402


def test_presenter_formats_supported_counters_durations_and_outcome() -> None:
    rows = present_request_metrics(
        {
            "model_rounds": 2,
            "tool_calls": 1,
            "provider_ms": 1840,
            "total_ms": 2470,
            "outcome": "success",
        }
    )

    assert rows == [
        {"label": "Model rounds", "value": "2"},
        {"label": "Tool calls", "value": "1"},
        {"label": "Provider", "value": "1.8 s"},
        {"label": "Total", "value": "2.5 s"},
        {"label": "Outcome", "value": "success"},
    ]


def test_presenter_omits_zero_unavailable_and_negative_values() -> None:
    assert present_request_metrics(
        {
            "model_rounds": 0,
            "tool_calls": None,
            "provider_ms": -1,
            "total_ms": "bad",
        }
    ) == []


def test_presenter_ignores_unknown_dynamic_or_private_keys() -> None:
    rows = present_request_metrics(
        {
            "model_rounds": 1,
            "prompt": "turn off the bedroom light",
            "session_id": "private-session",
            "device_name": "Bedroom Light",
            "tool_arguments": {"device": "Bedroom Light"},
            "custom_metric_user_input": 99,
        }
    )

    assert rows == [{"label": "Model rounds", "value": "1"}]
    assert "Bedroom" not in repr(rows)
    assert "private-session" not in repr(rows)


def test_presenter_rejects_non_mapping_and_unknown_outcome() -> None:
    assert present_request_metrics(None) == []
    assert present_request_metrics([]) == []
    assert present_request_metrics({"outcome": "other"}) == []


def test_millisecond_values_remain_compact() -> None:
    assert present_request_metrics({"mcp_ms": 48.6}) == [
        {"label": "MCP", "value": "49 ms"}
    ]
