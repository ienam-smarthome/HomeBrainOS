from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

from mcp_state_broker import _safe_trace_arguments
from request_tracing import _performance


def test_safe_trace_arguments_keeps_read_shape():
    result = _safe_trace_arguments(
        {
            "detailed": False,
            "format": "summary",
            "capabilityFilter": "Power Meter",
            "fields": ["id", "label", "currentStates"],
            "secret": "must-not-appear",
        }
    )

    assert result == {
        "detailed": False,
        "format": "summary",
        "capabilityFilter": "Power Meter",
        "fields": ["id", "label", "currentStates"],
    }


def test_performance_exposes_compact_mcp_events():
    trace = {
        "trace_id": "abc123",
        "route_selected": "mcp-fast",
        "route_reason": "test",
        "elapsed_ms": 10,
        "mcp_events": [
            {
                "tool": "hub_list_devices",
                "cache": "hit",
                "duration_ms": 0,
                "age_ms": 100,
                "arguments": {
                    "detailed": False,
                    "format": "summary",
                },
            }
        ],
    }

    performance = _performance(
        trace,
        {"route": "mcp-power-summary"},
    )

    assert performance["mcp_events"] == [
        {
            "tool": "hub_list_devices",
            "cache": "hit",
            "duration_ms": 0,
            "age_ms": 100,
            "arguments": {
                "detailed": False,
                "format": "summary",
            },
        }
    ]
