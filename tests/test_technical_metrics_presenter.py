from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from technical_metrics_presenter import present_request_metrics  # noqa: E402


def test_presenter_formats_production_snapshot() -> None:
    rows = present_request_metrics(
        {
            "outcome": "success",
            "counters": {"model_rounds": 2, "tool_calls": 1},
            "timings_ms": {"provider": 1840, "total": 2470},
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
            "counters": {"model_rounds": 0, "tool_calls": None},
            "timings_ms": {"provider": -1, "total": "bad"},
        }
    ) == []


def test_presenter_ignores_unknown_dynamic_or_private_keys() -> None:
    rows = present_request_metrics(
        {
            "counters": {"model_rounds": 1, "custom_metric_user_input": 99},
            "timings_ms": {},
            "prompt": "turn off the bedroom light",
            "session_id": "private-session",
            "device_name": "Bedroom Light",
            "tool_arguments": {"device": "Bedroom Light"},
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
    assert present_request_metrics({"timings_ms": {"mcp": 48.6}}) == [
        {"label": "MCP", "value": "49 ms"}
    ]


def test_refused_outcome_and_production_counter_names_are_supported() -> None:
    assert present_request_metrics(
        {
            "outcome": "refused",
            "counters": {
                "confirmation_expired": 1,
                "device_resolution_ambiguous": 2,
            },
            "timings_ms": {"tool_discovery": 250},
        }
    ) == [
        {"label": "Confirmations expired", "value": "1"},
        {"label": "Ambiguous resolutions", "value": "2"},
        {"label": "Discovery", "value": "250 ms"},
        {"label": "Outcome", "value": "refused"},
    ]
