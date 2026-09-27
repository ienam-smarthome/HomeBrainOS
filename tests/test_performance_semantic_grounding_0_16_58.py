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


def test_live_01657_run_one_localizes_mechanisms_and_preserves_table() -> None:
    draft = """The hub is **not currently overloaded**. All high-load health alerts are `false`, and free memory is healthy at approximately **819 MB**.

However, measured performance statistics identify several components that are consuming disproportionate resources. While they aren't causing a crash now, they are the most likely candidates to cause "lag" or instability if their activity increases.

### 🚩 Primary Resource Consumers

#### 1. Devices (Execution Lag & Volume)
*   **LG webOS TV**: This is the most critical performance outlier. It has an average execution time of **3,090ms (over 3 seconds)** per call. Such high latency typically indicates network timeouts or slow API responses from the TV, which can block hub execution threads and cause other automations to feel sluggish.
*   **Fan Switch (Tuya Local)**: High load (**12.9% busy**) driven by a very high call volume (14,293 calls).
*   **Matter Halo3000x Liv Socket**: High call volume (15,461 calls). Frequent reporting from power-monitoring sockets is a common cause of event-bus congestion.

#### 2. Apps (CPU & Memory Load)
*   **MCP Rule Server**: The highest app load (**17.8% busy**) with a high average execution time of **727ms**.
*   **SenseCap D1 Settings**: High load (**16.3% busy**) driven by an extreme call count of **56,962**. This suggests the app is polling or pushing configurations far too frequently.
*   **00 Life360 Connect & 08. Octopus Energy**: Both are contributing significant load (**13-15% busy**), likely due to frequent cloud polling.

### 🛠️ Recommended Optimisations

| Component | Action | Expected Impact |
| :--- | :--- | :--- |
| **LG webOS TV** | Ensure rules use asynchronous calls or generous timeouts. | Lower Hub Lag |
| **SenseCap D1** | Review the SenseCap D1 Settings app to see if polling intervals or configuration push frequencies can be reduced. | Lower CPU Usage |
| **Power Sockets** | Set a reporting threshold, e.g. 5W, or a longer reporting interval, e.g. 60s instead of 10s. | Less Event Congestion |
| **Cloud Apps** | Review the polling intervals for Life360 and Octopus Energy to ensure they aren't updating more often than necessary. | Lower CPU Usage |
| **MCP Rules** | Audit rules triggered by high-frequency sensors. Ensure rules aren't running complex logic every time a power value changes by 1 watt. | Lower App Execution Time |
"""

    corrected, changed = guard_performance_log_causality(draft, PERFORMANCE_ONLY_EVIDENCE)

    assert changed is True
    assert "3,090ms" in corrected
    assert "12.9% busy" in corrected
    assert "14,293" in corrected
    assert "15,461" in corrected
    assert "17.8% busy" in corrected
    assert "727ms" in corrected
    assert "16.3% busy" in corrected
    assert "56,962" in corrected
    assert "13-15% busy" in corrected

    assert "typically indicates network timeouts" not in corrected
    assert "common cause of event-bus congestion" not in corrected
    assert "This suggests the app is polling" not in corrected
    assert "likely due to frequent cloud polling" not in corrected
    assert "most likely candidates to cause" not in corrected

    rows = [line for line in corrected.splitlines() if line.startswith("|")]
    assert len(rows) == 7
    assert all(line.endswith("|") for line in rows)
    assert "| **LG webOS TV** | Inspect the cited integration implementation/configuration first." in corrected
    assert "| **SenseCap D1** | Inspect the cited integration/device configuration first." in corrected
    assert "| **Power Sockets** | Inspect the cited integration/device configuration first." in corrected
    assert "| **Cloud Apps** | Inspect the cited integration/device configuration first." in corrected
    assert "| **MCP Rules** | Inspect the cited automation configuration first." in corrected
    assert "5W" not in corrected
    assert "60s instead of 10s" not in corrected


def test_live_01657_run_two_wording_variants_are_grounded() -> None:
    draft = """### 🚩 Primary Resource Consumers
* **LG webOS TV**: It has an average execution time of **3,090ms (over 3 seconds)** per call. Such high latency typically indicates network timeouts or slow API responses from the TV, which can block hub execution threads and cause other automations to feel sluggish.
* **SenseCap D1 Settings**: High load (**16.3% busy**) driven by an extreme call count of **56,962**. Configuration push frequencies can be reduced to lower CPU usage.

### 🛠️ Recommended Optimisations

| Component | Action | Expected Impact |
| :--- | :--- | :--- |
| **LG webOS TV** | Investigate the driver/integration settings for timeouts or sync/async behavior. The 3-second average execution time is the primary source of potential hub stutter. | Lower Hub Lag |
| **SenseCap D1** | Review the SenseCap D1 Settings app to see if polling intervals or configuration push frequencies can be reduced. | Lower CPU Usage |
| **Cloud Apps** | Review the polling intervals for Life360 and Octopus Energy to ensure they aren't updating more often than necessary. | Lower CPU Usage |
| **MCP Rules** | Audit rules triggered by high-frequency sensors. Ensure rules aren't running complex logic every time a power value changes by a small amount. | Lower App Execution Time |
"""

    corrected, changed = guard_performance_log_causality(draft, PERFORMANCE_ONLY_EVIDENCE)

    assert changed is True
    assert "3,090ms" in corrected
    assert "16.3% busy" in corrected
    assert "56,962" in corrected
    assert "typically indicates network timeouts" not in corrected
    assert "primary source of potential hub stutter" not in corrected
    assert "Review the polling intervals" not in corrected
    assert "configuration push frequencies can be reduced" not in corrected.split("### 🛠️ Recommended Optimisations", 1)[1]
    assert "Ensure rules aren't running complex logic every time" not in corrected
    assert "| **LG webOS TV** | Inspect the cited integration implementation/configuration first." in corrected
    assert "| **SenseCap D1** | Inspect the cited integration/device configuration first." in corrected
    assert "| **Cloud Apps** | Inspect the cited integration/device configuration first." in corrected
    assert "| **MCP Rules** | Inspect the cited automation configuration first." in corrected


def test_measured_bullet_survives_when_unsupported_clause_is_localized() -> None:
    draft = """### Primary Resource Consumers
* **SenseCap D1 Settings**: High load (**16.3% busy**) driven by an extreme call count of **56,962**. This suggests the app is polling or pushing configurations far too frequently.

### Recommended Optimisations
* Inspect the measured high-volume component before tuning it.
"""

    corrected, changed = guard_performance_log_causality(draft, PERFORMANCE_ONLY_EVIDENCE)

    assert changed is True
    assert "**SenseCap D1 Settings**" in corrected
    assert "16.3% busy" in corrected
    assert "56,962" in corrected
    assert "This suggests the app is polling" not in corrected
    assert "implementation hypothesis worth investigating" in corrected


def test_conditional_mechanism_analysis_remains_allowed() -> None:
    draft = """### Primary Resource Consumers
* **LG webOS TV**: Average execution time is 3 seconds per call.

### Observations & Hypotheses
Long calls could block execution threads if calls are synchronous.

### Recommended Optimisations
* Inspect the LG integration implementation before changing it.
"""

    corrected, changed = guard_performance_log_causality(draft, PERFORMANCE_ONLY_EVIDENCE)

    assert changed is False
    assert corrected == draft
