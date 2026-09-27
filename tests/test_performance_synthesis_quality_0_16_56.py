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


def test_live_01655_tv_async_timeout_prescription_is_grounded() -> None:
    draft = """### Recommended Optimizations
* **Audit TV Integration**: Since the LG TV is very slow to respond, ensure that any rules involving the TV use asynchronous calls or have generous timeouts to prevent them from slowing down other hub operations.
"""

    corrected, changed = guard_performance_log_causality(draft, EVIDENCE)

    assert changed is True
    assert "**Audit TV Integration**:" in corrected
    assert "ensure that any rules" not in corrected
    assert "generous timeouts" not in corrected
    assert "Inspect the cited integration implementation/configuration first" in corrected
    assert "driver/app code or settings" in corrected


def test_conditional_tv_latency_observation_remains_allowed() -> None:
    draft = (
        "### Top Resource Consumers\n"
        "LG webOS TV is 16.2% busy with about 3 seconds per call.\n\n"
        "### Observations & Hypotheses\n"
        "The long calls can block execution threads if calls are synchronous.\n\n"
        "### Recommended Optimizations\n"
        "* Inspect the LG integration implementation before changing it."
    )

    corrected, changed = guard_performance_log_causality(draft, EVIDENCE)

    assert changed is False
    assert corrected == draft


def test_missing_action_section_gets_grounded_process_actions() -> None:
    draft = """### Top Resource Consumers
**Devices:** LG webOS TV is 16.2% busy at about 3 seconds per call.
**Apps:** SenseCap D1 Settings has the highest call volume.

### Observations & Hypotheses
Recent logs show frequent device events, but they do not prove the cause of the measured totals.
"""

    corrected, changed = guard_performance_log_causality(draft, EVIDENCE)

    assert changed is True
    assert "### Grounded Next Actions" in corrected
    assert "**High per-call latency:**" in corrected
    assert "**High call volume:**" in corrected
    assert "only prescribe async/sync" in corrected
    assert "only prescribe a specific interval/frequency change" in corrected


def test_existing_recommendation_section_is_not_duplicated() -> None:
    draft = """### Top Resource Consumers
LG webOS TV is 16.2% busy.

### Observations & Hypotheses
The recent logs are observations only.

### Recommended Optimizations
* Inspect the measured high-latency component first.
"""

    corrected, changed = guard_performance_log_causality(draft, EVIDENCE)

    assert changed is False
    assert corrected == draft
    assert "Grounded Next Actions" not in corrected


def test_current_turn_code_read_allows_specific_implementation_advice() -> None:
    evidence = EVIDENCE + [
        {
            "sub_tool": "hub_get_app_code",
            "success": True,
            "evidence_kind": "app_code",
            "arguments": {"tool": "hub_get_app_code", "args": {"appId": 123}},
        }
    ]
    draft = """### Recommended Optimizations
* **Audit TV Integration**: Ensure that the integration uses asynchronous calls and adjust its timeout if the inspected code shows a blocking network path.
"""

    corrected, changed = guard_performance_log_causality(draft, evidence)

    assert changed is False
    assert corrected == draft
