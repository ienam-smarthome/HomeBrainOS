from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "summarize_request_trace_metrics.py"


def _module():
    spec = importlib.util.spec_from_file_location("request_trace_metrics", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summarize_accepts_performance_wrapped_trace_records():
    result = _module().summarize(
        {
            "traces": [
                {"performance": {"mcp_calls": 2, "mcp_duration_ms": 100, "elapsed_ms": 300}},
                {"performance": {"mcp_calls": 1, "mcp_duration_ms": 50, "elapsed_ms": 200}},
            ]
        }
    )

    assert result == {
        "request_count": 2,
        "mean_mcp_calls": 1.5,
        "total_mcp_calls": 3.0,
        "mean_mcp_duration_ms": 75.0,
        "total_mcp_duration_ms": 150.0,
        "mean_elapsed_ms": 250.0,
    }


def test_compare_reports_after_minus_before_without_claiming_improvement():
    module = _module()
    result = module.compare(
        [{"mcp_calls": 3, "mcp_duration_ms": 120, "elapsed_ms": 400}],
        [{"mcp_calls": 2, "mcp_duration_ms": 80, "elapsed_ms": 300}],
    )

    assert result["delta_after_minus_before"]["mean_mcp_calls"] == -1.0
    assert result["delta_after_minus_before"]["mean_mcp_duration_ms"] == -40.0
    assert result["delta_after_minus_before"]["mean_elapsed_ms"] == -100.0
