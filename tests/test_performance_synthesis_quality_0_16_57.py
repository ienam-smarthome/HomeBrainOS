from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from performance_causality_guard import guard_performance_log_causality  # noqa: E402


PERFORMANCE_ONLY_EVIDENCE = [
    {
        "sub_tool": "hub_get_metrics",
        "success": True,
        "arguments": {"tool": "hub_get_metrics"},
    },
    {
        "sub_tool": "hub_get_performance_stats",
        "success": True,
        "arguments": {"tool": "hub_get_performance_stats", "args": {"type": "app"}},
    },
    {
        "sub_tool": "hub_get_performance_stats",
        "success": True,
        "arguments": {"tool": "hub_get_performance_stats", "args": {"type": "device"}},
    },
]

PERFORMANCE_AND_LOG_EVIDENCE = PERFORMANCE_ONLY_EVIDENCE + [
    {
        "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool": "hub_get_logs"},
        "details": {"logs": []},
    }
]


def test_performance_only_live_answer_gets_grounded_next_actions() -> None:
    draft = """The hub is not currently overloaded.

### Potential App Culprits
* **SenseCap D1 Settings**: Highest overall load (17.0% busy) driven by a high call count.

### Potential Device Culprits
* **LG webOS TV**: Average execution time is over 3 seconds per call.
"""

    corrected, changed = guard_performance_log_causality(
        draft,
        PERFORMANCE_ONLY_EVIDENCE,
    )

    assert changed is True
    assert "### Grounded Next Actions" in corrected
    assert "**High per-call latency:**" in corrected
    assert "**High call volume:**" in corrected
    assert "recent logs" not in corrected.casefold()


def test_live_01656_markdown_table_rewrite_preserves_table_shape() -> None:
    draft = """### Recommended Optimisations

| Component | Action | Expected Impact |
| :--- | :--- | :--- |
| **LG webOS TV** | Ensure rules use asynchronous calls or generous timeouts. | Lower latency |
| **SenseCap D1** | Review the app configuration. Reduce the frequency of config pushes or polling intervals. | Lower CPU |
| **Power Sockets** | Set a reporting threshold, e.g. 5W, or a longer reporting interval, e.g. 60s instead of 10s. | Less event traffic |
| **MCP Rules** | Ensure rules aren't running complex logic every 10 seconds. | Lower app time |
"""

    corrected, changed = guard_performance_log_causality(
        draft,
        PERFORMANCE_AND_LOG_EVIDENCE,
    )

    assert changed is True
    rows = [line for line in corrected.splitlines() if line.startswith("|")]
    assert len(rows) == 6
    assert all(line.endswith("|") for line in rows)
    assert "| **LG webOS TV** | Inspect the cited integration implementation/configuration first." in corrected
    assert "| **SenseCap D1** | Inspect the cited integration/device configuration first." in corrected
    assert "| **Power Sockets** | Inspect the cited integration/device configuration first." in corrected
    assert "| **MCP Rules** | Inspect the cited automation configuration first." in corrected
    assert "5W" not in corrected
    assert "60s instead of 10s" not in corrected


def test_live_01656_unproven_implementation_mechanisms_are_downgraded() -> None:
    draft = """### Primary Resource Consumers
* **LG webOS TV**: Average execution time is 3,073ms. Such high latency often indicates network timeouts or slow API responses from the TV, which can block hub execution threads and cause lag for other devices.
* **SenseCap D1 Settings**: 16.9% busy with 48,364 calls. This suggests the app is polling or pushing configurations far too frequently.
* **Life360 & Octopus Energy**: Both contribute significant measured load, likely due to frequent cloud polling for location and energy data.

### Recommended Optimisations
* Inspect the measured high-latency and high-volume components first.
"""

    corrected, changed = guard_performance_log_causality(
        draft,
        PERFORMANCE_ONLY_EVIDENCE,
    )

    assert changed is True
    assert "often indicates network timeouts" not in corrected
    assert "This suggests the app is polling" not in corrected
    assert "likely due to frequent cloud polling" not in corrected
    assert "implementation hypothesis worth investigating" in corrected
    assert "implementation cause of that measured load is not established" in corrected
    assert "3,073ms" in corrected
    assert "16.9% busy" in corrected


def test_conditional_synchronous_analysis_remains_allowed_without_code_read() -> None:
    draft = """### Primary Resource Consumers
* **LG webOS TV**: Average execution time is 3 seconds per call.

### Observations & Hypotheses
Long calls could block execution threads if calls are synchronous.

### Recommended Optimisations
* Inspect the LG integration implementation before changing it.
"""

    corrected, changed = guard_performance_log_causality(
        draft,
        PERFORMANCE_ONLY_EVIDENCE,
    )

    assert changed is False
    assert corrected == draft


def test_code_read_allows_specific_mechanism_and_tuning_advice() -> None:
    evidence = PERFORMANCE_ONLY_EVIDENCE + [
        {
            "sub_tool": "hub_get_driver_code",
            "success": True,
            "evidence_kind": "driver_code",
            "arguments": {"tool": "hub_get_driver_code", "args": {"deviceId": 1}},
        }
    ]
    draft = """### Recommended Optimisations
* **LG webOS TV**: The inspected driver uses synchronous network calls; switch this path to async and increase its timeout to 10 seconds.
"""

    corrected, changed = guard_performance_log_causality(draft, evidence)

    assert changed is False
    assert corrected == draft
