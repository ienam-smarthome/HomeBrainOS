from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from performance_causality_guard import guard_performance_log_causality  # noqa: E402


BASE_EVIDENCE = [
    {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_performance_stats",
        "success": True,
        "arguments": {"tool": "hub_get_performance_stats"},
    },
    {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool": "hub_get_logs", "args": {"limit": 100}},
        "details": {
            "thresholdSamples": [
                {
                    "source": "Power saving: TV OFF (medium setting)",
                    "operator": ">=",
                    "threshold": 65,
                    "values": [62, 66, 69, 77],
                    "minObserved": 55,
                    "maxObserved": 81,
                    "qualifyingCount": 20,
                    "nonQualifyingCount": 6,
                    "allQualifying": False,
                    "observedValueCount": 26,
                }
            ],
            "logs": [],
        },
    },
]


LIVE_01653_RECOMMENDATIONS = """### Recommended Optimizations
* **Fix the TV Power Rule**: Edit the `Power saving: TV OFF (medium setting)` rule to include a **duration** (e.g., "Power >= 65W for 2 minutes") or a wider **hysteresis gap** to prevent the rule from rapidly cycling on minor power fluctuations.
* **Dampen Kitchen Sensor**: Check the settings for the `Linptech Kitchen sensor`. If possible, increase the "blind time" or "occupancy timeout" to reduce the frequency of events.
* **Adjust Energy Reporting**: If the `Halo3000x` or `Octopus` integrations allow, increase the reporting interval for power updates to every 1-5 minutes unless real-time precision is critical.
"""


def test_live_01653_exact_configuration_edits_are_blocked_without_config_read() -> None:
    corrected, changed = guard_performance_log_causality(
        LIVE_01653_RECOMMENDATIONS,
        BASE_EVIDENCE,
    )

    assert changed is True
    assert "Power >= 65W for 2 minutes" not in corrected
    assert "wider **hysteresis gap**" not in corrected
    assert "increase the \"blind time\"" not in corrected
    assert "increase the reporting interval" not in corrected
    assert "Inspect the cited automation configuration first" in corrected
    assert "Inspect the cited sensor configuration first" in corrected
    assert "Inspect the cited integration/device configuration first" in corrected


def test_configuration_read_allows_specific_configuration_recommendations() -> None:
    evidence = BASE_EVIDENCE + [
        {
            "tool": "hub_read_apps_code",
            "sub_tool": "hub_get_rule_details",
            "success": True,
            "evidence_kind": "rule_configuration",
            "arguments": {"tool": "hub_get_rule_details", "args": {"appId": 2817}},
        }
    ]

    corrected, changed = guard_performance_log_causality(
        LIVE_01653_RECOMMENDATIONS,
        evidence,
    )

    assert changed is False
    assert corrected == LIVE_01653_RECOMMENDATIONS


def test_cautious_non_prescriptive_review_language_is_preserved() -> None:
    draft = (
        "The TV rule is worth inspecting to see whether its current configuration "
        "has suitable debounce or hysteresis controls."
    )

    corrected, changed = guard_performance_log_causality(draft, BASE_EVIDENCE)

    assert changed is False
    assert corrected == draft
