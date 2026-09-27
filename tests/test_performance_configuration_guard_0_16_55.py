from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from performance_causality_guard import guard_performance_log_causality  # noqa: E402


EVIDENCE = [
    {
        "sub_tool": "hub_get_performance_stats",
        "success": True,
        "arguments": {"tool": "hub_get_performance_stats"},
    },
    {
        "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool": "hub_get_logs"},
        "details": {"logs": []},
    },
]


def test_live_01654_guard_preserves_distinct_recommendation_labels() -> None:
    draft = """### Recommended Optimizations
* **Dampen Kitchen Sensor**: Check the settings for the `Linptech Kitchen sensor`. If possible, increase the "blind time" or "occupancy timeout" to reduce the frequency of events.
* **Adjust Energy Reporting**: If the `Halo3000x` or `Octopus` integrations allow, increase the reporting interval for power updates to every 1–5 minutes unless real-time precision is critical.
"""

    corrected, changed = guard_performance_log_causality(draft, EVIDENCE)

    assert changed is True
    assert "**Dampen Kitchen Sensor**:" in corrected
    assert "**Adjust Energy Reporting**:" in corrected
    assert "Inspect the cited sensor configuration first." in corrected
    assert "Inspect the cited integration/device configuration first." in corrected
    assert "every 1–5 minutes" not in corrected
    assert corrected.count("**Dampen Kitchen Sensor**:") == 1
    assert corrected.count("**Adjust Energy Reporting**:") == 1
    assert len({line for line in corrected.splitlines() if line.startswith("*")}) == 2


def test_automation_replacement_keeps_original_recommendation_label() -> None:
    draft = """### Recommended Optimizations
* **Fix the TV Power Rule**: Edit the `Power saving: TV OFF (medium setting)` rule to include a duration (e.g. Power >= 65W for 2 minutes) or a wider hysteresis gap.
"""

    corrected, changed = guard_performance_log_causality(draft, EVIDENCE)

    assert changed is True
    assert "**Fix the TV Power Rule**:" in corrected
    assert "Inspect the cited automation configuration first." in corrected
    assert "2 minutes" not in corrected
