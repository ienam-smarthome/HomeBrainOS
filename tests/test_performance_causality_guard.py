from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from final_answer_coordinator import FinalAnswerCoordinator  # noqa: E402
from performance_causality_guard import (  # noqa: E402
    guard_performance_log_causality,
    performance_validation_needed,
)


PERFORMANCE_AND_LOG_EVIDENCE = [
    {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_performance_stats",
        "success": True,
        "arguments": {
            "tool": "hub_get_performance_stats",
            "args": {"type": "device", "sortBy": "busyPercent"},
        },
    },
    {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool": "hub_get_logs", "args": {"since": "30m"}},
        "details": {
            "logs": [
                {
                    "message": (
                        "app|2817|Power saving: TV OFF (medium setting)|"
                        "Triggered: Power level of TV(79) reported >= 65.0"
                    )
                },
                {
                    "message": (
                        "app|2817|Power saving: TV OFF (medium setting)|"
                        "Action: Wait for event: Power level of TV(79) is <= 50.0 "
                        "and stays that way for: 0:03:00"
                    )
                },
                {
                    "message": (
                        "app|2817|Power saving: TV OFF (medium setting)|"
                        "Event: TV power 79"
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
                        "Event: TV power 72"
                    )
                },
            ]
        },
    },
]

STRUCTURED_01651_EVIDENCE = [
    PERFORMANCE_AND_LOG_EVIDENCE[0],
    {
        "tool": "hub_read_diagnostics",
        "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool": "hub_get_logs", "args": {"limit": 100}},
        "details": {
            "logCount": 100,
            "logs": [
                {"message": f"device|{index}|Noise|unrelated row {index}"}
                for index in range(20)
            ],
            "thresholdSamples": [
                {
                    "source": "Power saving: TV OFF (medium setting)",
                    "operator": ">=",
                    "threshold": 65.0,
                    "values": [87.0, 84.0, 80.0],
                    "allQualifying": True,
                    "observedValueCount": 3,
                }
            ],
        },
    },
]

BAD_01648_DRAFT = """The hub is not currently overloaded.

### Root Causes (from Logs)
The logs reveal three specific patterns driving this load:

1. **TV Power Trigger Loop**: Because the TV power is fluctuating slightly around that 65W mark, the rule is constantly restarting, which is likely driving the high busy percentage for the LG TV.

### Recommended Optimizations
* **Fix the TV Rule**: Modify `Power saving: TV OFF (medium setting)`. Instead of triggering immediately at 65W, add a **stays that way for** duration of 1 minute.
"""

BAD_01651_DRAFT = """LG webOS TV is still the main device-side concern at 16.3% busy and about 3 seconds per call.

The recent TV rule logs show power moving 87 -> 84 -> 80 W, fluctuating around the 65 W threshold. This is a likely hypothesis for the high busy percentage.

The TV rule needs a debounce or larger gap between trigger actions.
"""

CLAUDE_STYLE_CAUSAL_LEAP = """LG webOS TV is top device by load at 16.3% busy, averages 3,066 ms per call, and has been stale for 929 hours. This strongly suggests the driver is repeatedly trying to reach a TV that is not responding and timing out on each attempt, making it a hidden overload source.
"""


def test_performance_validation_requires_stats_and_logs() -> None:
    assert performance_validation_needed(PERFORMANCE_AND_LOG_EVIDENCE)
    assert not performance_validation_needed(PERFORMANCE_AND_LOG_EVIDENCE[:1])
    assert not performance_validation_needed(PERFORMANCE_AND_LOG_EVIDENCE[1:])


def test_live_01648_log_causality_is_localized() -> None:
    corrected, changed = guard_performance_log_causality(
        BAD_01648_DRAFT,
        PERFORMANCE_AND_LOG_EVIDENCE,
    )

    assert changed is True
    assert "Root Causes (from Logs)" not in corrected
    assert "Recent log observations (not proven performance causes)" in corrected
    assert "likely driving the high busy percentage" not in corrected
    assert "do not establish that it causes the measured performance result" in corrected
    assert "qualifying values without evidence of threshold crossing" in corrected
    assert "did not read the rule/app configuration" in corrected


def test_live_01651_structured_full_log_sample_repairs_threshold_and_prescription() -> None:
    corrected, changed = guard_performance_log_causality(
        BAD_01651_DRAFT,
        STRUCTURED_01651_EVIDENCE,
    )

    assert changed is True
    assert "fluctuating around the 65 W threshold" not in corrected
    assert "qualifying values without evidence of threshold crossing" in corrected
    assert "likely hypothesis for the high busy percentage" not in corrected
    assert "hypothesis worth investigating" in corrected
    assert "needs a debounce or larger gap" not in corrected
    assert "did not read the rule/app configuration" in corrected


def test_structured_full_sample_overrides_misleading_excerpt() -> None:
    evidence = [
        PERFORMANCE_AND_LOG_EVIDENCE[0],
        {
            "tool": "hub_read_diagnostics",
            "sub_tool": "hub_get_logs",
            "success": True,
            "details": {
                "logs": PERFORMANCE_AND_LOG_EVIDENCE[1]["details"]["logs"],
                "thresholdSamples": [
                    {
                        "source": "Power saving: TV OFF (medium setting)",
                        "operator": ">=",
                        "threshold": 65.0,
                        "values": [79.0, 75.0, 58.0],
                        "allQualifying": False,
                        "observedValueCount": 3,
                    }
                ],
            },
        },
    ]
    draft = "The TV power is fluctuating around the 65 W threshold."

    corrected, changed = guard_performance_log_causality(draft, evidence)

    assert changed is False
    assert corrected == draft


def test_claude_style_timeout_cause_is_kept_as_hypothesis_not_fact() -> None:
    corrected, changed = guard_performance_log_causality(
        CLAUDE_STYLE_CAUSAL_LEAP,
        STRUCTURED_01651_EVIDENCE,
    )

    assert changed is True
    assert "hidden overload source" not in corrected
    assert "plausible hypothesis to verify" in corrected
    assert "not a proven source" in corrected


def test_safe_performance_observations_are_unchanged() -> None:
    safe = (
        "LG webOS TV measured 16.6% busy at about 3 seconds per call. "
        "Separately, recent logs show the TV power rule triggering repeatedly. "
        "The current evidence does not establish that the rule caused the driver timing."
    )
    corrected, changed = guard_performance_log_causality(
        safe,
        PERFORMANCE_AND_LOG_EVIDENCE,
    )
    assert changed is False
    assert corrected == safe


@pytest.mark.asyncio
async def test_non_investigative_performance_answer_gets_repair_and_final_guard() -> None:
    calls: list[tuple[list[dict[str, object]], list[dict[str, object]]]] = []

    async def chat(messages, tools):
        calls.append((messages, tools))
        # Simulate a provider that ignores both the original policy and the repair.
        return {"role": "assistant", "content": BAD_01648_DRAFT}

    coordinator = FinalAnswerCoordinator(
        chat,
        evidence_supplier=lambda: PERFORMANCE_AND_LOG_EVIDENCE,
    )
    answer = await coordinator.answer(
        [{"role": "user", "content": "What extra performance improvements can be made?"}]
    )

    assert len(calls) == 2
    assert "HOST SYNTHESIS VALIDATION REPAIR" in str(calls[1][0][-1]["content"])
    assert "performance_log_causality" in str(calls[1][0][-1]["content"])
    assert "Root Causes (from Logs)" not in answer
    assert "likely driving the high busy percentage" not in answer
    assert "not proven performance causes" in answer
