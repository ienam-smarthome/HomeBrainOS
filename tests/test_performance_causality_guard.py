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

BAD_01648_DRAFT = """The hub is not currently overloaded.

### Root Causes (from Logs)
The logs reveal three specific patterns driving this load:

1. **TV Power Trigger Loop**: Because the TV power is fluctuating slightly around that 65W mark, the rule is constantly restarting, which is likely driving the high busy percentage for the LG TV.

### Recommended Optimizations
* **Fix the TV Rule**: Modify `Power saving: TV OFF (medium setting)`. Instead of triggering immediately at 65W, add a **stays that way for** duration of 1 minute.
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
    assert "do not establish oscillation across the trigger threshold" in corrected
    assert "did not read the rule/app configuration" in corrected


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
