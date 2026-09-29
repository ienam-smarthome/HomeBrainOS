from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from performance_live_semantic_guard import guard_live_performance_semantics  # noqa: E402


def _receipt(tool: str, sub_tool: str, *, kind: str = "tool_result") -> dict:
    return {
        "tool": tool,
        "sub_tool": sub_tool,
        "success": True,
        "supports_live_claim": True,
        "evidence_kind": kind,
        "arguments": {"tool": sub_tool},
        "summary": "successful read",
    }


def _performance_evidence() -> list[dict]:
    return [
        _receipt("hub_read_diagnostics", "hub_get_metrics"),
        _receipt("hub_manage_logs", "hub_get_performance_stats"),
        _receipt("hub_manage_logs", "hub_get_jobs"),
        _receipt("hub_manage_logs", "hub_get_logs", kind="performance_api_recent_logs"),
    ]


LIVE_01670 = '''### Hubitat Performance Analysis

Your hub's core resources are healthy, but there are significant bottlenecks caused by blocking device calls and synchronized scheduling.

#### 🟢 Hub Health & Resources
*   **Memory & Temperature:** Excellent. You have **~962MB of free memory** and an internal temperature of **45.3°C**.
*   **Database:** Measured at **198MB**, which is well within normal limits.
*   **System State:** The hub is not in safe mode, and no high-load alerts are active.

#### ⚠️ Performance Outliers

**1. Scheduling "Thunder-Claps" (Job Synchronization)**
There is a severe synchronization of scheduled jobs occurring at the top of the minute. At **14:01:00 BST**, the hub attempts to execute:
*   **Dozens of `sessionTick` jobs** for "Block [Device]" (e.g., *Phone-Runa-Pixel-9a*, *Tab-S9-FE*, *Home-Assistant*).
*   **Multiple `autoPoll` jobs** (Eufy Robovac socket, Nest Mini socket, Computer).
*   **Octopus Energy `scheduledLiveHeartbeat`**.
Executing this many jobs on the exact same second creates CPU spikes that can cause UI stuttering or delayed automation triggers.

**2. Blocking Device Execution**
Two devices are significantly blocking hub threads due to extremely high average execution times:
*   **LG webOS TV:** Average execution time of **3,040ms** (16% busy).
*   **OpenWeatherMap Multi-API:** Average execution time of **2,969ms**.
Execution times of ~3 seconds are "blocking" behaviors that can stall other hub operations.

**3. High-Frequency Reporting & Overhead**
*   **⚛️ Matter Halo3000x Liv Socket:** This device is highly active with **6,371 calls**. Logs show it reporting power updates multiple times within a few seconds, adding constant overhead.
*   **Fan Switch (Tuya Local):** Consumes **11.3%** of processing time with **4,951 calls**.

**4. System Warnings**
*   **Z-Wave Health:** The Hub Info device reports `zwHealthy : false`.
*   **Connectivity:** The `SenseCap D1 Settings` app is reporting "No route to host (Host unreachable)" errors.
*   **Internal Latency:** The `MCP Rule Server` logged a slow internal GET request taking **9,003ms**.

### Recommended Improvements

| Priority | Target | Action |
| :--- | :--- | :--- |
| **High** | **"Block [Device]" Jobs** | Stagger the start times of these recurring jobs to avoid the simultaneous execution spike at the top of the minute. |
| **High** | **LG TV & Weather API** | **Investigate drivers/connectivity.** Check if the LG TV is offline or if the Weather API is timing out. These 3-second delays are the primary cause of thread blocking. |
| **Medium** | **Halo3000x Socket** | Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. |
| **Medium** | **Z-Wave Network** | **Run a Z-Wave repair.** Since `zwHealthy` is false, check for dead nodes or interference. |
| **Low** | **SenseCap D1** | Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. |'''


def test_01671_full_live_fixture_is_grounded_and_markdown_table_survives() -> None:
    corrected, changed = guard_live_performance_semantics(
        LIVE_01670,
        _performance_evidence(),
    )

    assert changed is True

    for unsafe in (
        "significant bottlenecks caused by blocking device calls",
        "creates CPU spikes",
        "UI stuttering or delayed automation triggers",
        "Blocking Device Execution",
        "blocking hub threads",
        '"blocking" behaviors',
        "stall other hub operations",
        "High-Frequency Reporting & Overhead",
        "adding constant overhead",
        "well within normal limits",
        "primary cause of thread blocking",
        "Run a Z-Wave repair",
        "Stagger the start times",
    ):
        assert unsafe not in corrected

    assert "198 MB" in corrected
    assert "does not establish a normal-size threshold" in corrected
    assert "does not establish thread blocking" in corrected
    assert "does not establish material CPU load" in corrected
    assert "does not establish that staggering is configurable" in corrected
    assert "does not establish that a repair is required" in corrected
    assert "does not establish that it adds material hub overhead" in corrected

    table_lines = [line for line in corrected.splitlines() if line.strip().startswith("|")]
    assert len(table_lines) == 7
    assert table_lines[0] == "| Priority | Target | Action |"
    assert table_lines[1] == "| :--- | :--- | :--- |"
    assert all(line.count("|") == 4 for line in table_lines)
    assert any('**"Block [Device]" Jobs**' in line for line in table_lines)
    assert any("staggering is configurable" in line for line in table_lines)
    assert any("**LG TV & Weather API**" in line for line in table_lines)
    assert any("**Z-Wave Network**" in line for line in table_lines)


def test_zwave_repair_is_only_allowed_with_zwave_specific_diagnostics() -> None:
    message = "| High | Z-Wave Network | Run a Z-Wave repair. |"

    blocked, blocked_changed = guard_live_performance_semantics(
        message,
        _performance_evidence(),
    )
    assert blocked_changed is True
    assert "Run a Z-Wave repair" not in blocked
    assert "does not establish that a repair is required" in blocked
    assert blocked.count("|") == 4

    diagnostic_evidence = [
        *_performance_evidence(),
        _receipt(
            "hub_read_diagnostics",
            "hub_get_zwave_node_details",
            kind="zwave_node_diagnostics",
        ),
    ]
    allowed, allowed_changed = guard_live_performance_semantics(
        message,
        diagnostic_evidence,
    )
    assert allowed_changed is False
    assert allowed == message
