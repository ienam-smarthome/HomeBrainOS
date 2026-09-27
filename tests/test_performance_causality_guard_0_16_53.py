from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from performance_causality_guard import guard_performance_log_causality  # noqa: E402


LIVE_01652_CROSSING_EVIDENCE = [
    {
        "tool": "hub_manage_logs",
        "sub_tool": "hub_get_performance_stats",
        "success": True,
        "arguments": {
            "tool": "hub_get_performance_stats",
            "args": {"type": "device", "sortBy": "pct", "limit": 10},
        },
    },
    {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
        "details": {
            "logCount": 100,
            "logs": [
                {
                    "message": (
                        "app|2817|Power saving: TV OFF (medium setting)|"
                        "Triggered: Power level of TV(75) reported >= 65.0"
                    )
                },
                {
                    "message": (
                        "app|2817|Power saving: TV OFF (medium setting)|"
                        "Event: TV power 75"
                    )
                },
                {
                    "message": (
                        "app|2817|Power saving: TV OFF (medium setting)|"
                        "Event: TV power 58"
                    )
                },
            ],
            "thresholdSamples": [
                {
                    "source": "Power saving: TV OFF (medium setting)",
                    "operator": ">=",
                    "threshold": 65,
                    "values": [58, 58, 61, 61, 58, 58, 55, 55, 59, 59, 75, 75],
                    "allQualifying": False,
                    "observedValueCount": 33,
                }
            ],
        },
    },
]


LIVE_01652_BAD_DRAFT = """### Observations & Hypotheses

1. **TV Power Trigger Loop (Confirmed Hypothesis)**: The app `Power saving: TV OFF (medium setting)` is triggering every few seconds. It triggers whenever the TV power is >= 65W, then starts a Wait for event for power <= 50W. Because the TV power is fluctuating slightly (e.g., 75W -> 68W -> 73W), the rule is constantly restarting. This is the primary driver for the high busy percentage of the LG TV.
"""


def test_live_01652_primary_driver_is_not_allowed_from_recent_logs() -> None:
    corrected, changed = guard_performance_log_causality(
        LIVE_01652_BAD_DRAFT,
        LIVE_01652_CROSSING_EVIDENCE,
    )

    assert changed is True
    assert "Confirmed Hypothesis" not in corrected
    assert "Hypothesis (cause unproven)" in corrected
    assert "primary driver for the high busy percentage" not in corrected
    assert "do not establish that it is a primary cause or driver" in corrected

    # This sample genuinely contains values on both sides of the 65 W trigger,
    # so the threshold wording is not rewritten merely because causality is.
    assert "fluctuating slightly" in corrected


def test_measured_primary_device_wording_is_not_overcorrected() -> None:
    draft = (
        "LG webOS TV is the primary device-side performance concern at 16.3% busy "
        "and about 3 seconds per call."
    )

    corrected, changed = guard_performance_log_causality(
        draft,
        LIVE_01652_CROSSING_EVIDENCE,
    )

    assert changed is False
    assert corrected == draft
