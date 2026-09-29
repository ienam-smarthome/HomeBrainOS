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


LIVE_01672 = '''### Hubitat Performance Analysis

The measured execution time warrants investigation, but this turn does not establish thread blocking, stalled hub operations, or a blocking implementation mechanism.

#### 🟢 System Health
*   **Resources:** The hub has **~1,016MB of free memory** and an internal temperature of **46.5°C**.
*   **Database:** The database size is **188MB**, which is well within healthy limits.
*   **Stability:** The hub is not in safe mode, and no high-load or low-memory alerts are active.

#### ⚠️ Performance Bottlenecks

**1. Blocking Device Execution (High Latency)**
The **LG webOS TV** is a significant performance outlier. It has an average execution time of **3,041ms**; this is a measured performance concern, but the current statistics do not establish that it; this is a measured performance concern, but the current statistics do not establish that it causes hub lag, stutter, congestion, or instability. The measured execution time warrants investigation, but this turn does not establish thread blocking, stalled hub operations, or a blocking implementation mechanism. (The **OpenWeatherMap Multi-API** also shows high average latency at **2,801ms**, though its overall impact is lower at 3.2% busy).

**2. Job Synchronization ("Thunder-Claps")**
Many scheduled jobs share the same scheduled timestamp occurring at the top of the minute. At **15:02:00 BST**, the hub is scheduled to execute:
*   **Dozens of `sessionTick` jobs** for "Block [Device]" (e.g., *Phone-Runa-Pixel-9a*, *Tab-S9-FE*, *Home-Assistant*).
*   **Multiple `autoPoll` jobs** (Eufy Robovac socket, Nest Mini socket, Computer).
*   **Octopus Energy `scheduledLiveHeartbeat`**.
Executing this many tasks on the exact same second creates CPU spikes that can lead to UI stuttering or delayed automation triggers.

**3. High-Frequency Reporting (Chatter)**
*   **⚛️ Matter Halo3000x Liv Socket:** This device is highly active with **6,783 calls**. Logs confirm it reports `ActivePower` approximately every 10 seconds, adding constant background overhead.
*   **Fan Switch (Tuya Local):** Consumes **11.4%** of processing time with **5,352 calls**.

**4. Connectivity Warnings**
Current logs indicate several communication failures:
*   **SenseCap D1 Settings:** "Config push failed (No route to host (Host unreachable))".
*   **Google TV Streamer (ADB):** "Shell timeout".
*   **00 Google Calendar Notifier:** Speech announcements on the Google Nest Hub were not confirmed playing after 3 attempts.

---

### 🛠️ Recommended Improvements

| Priority | Target | Action |
| :--- | :--- | :--- |
| **High** | **LG webOS TV** | **Investigate Connectivity.** The 3-second average execution time suggests the hub is timing out or struggling to reach the TV. Check the network stability or driver version. |
| **High** | **Scheduled Jobs** | Inspect the cited automation configuration first. Recent activity can justify an execution review, but this turn did not read the rule/app configuration needed to prescribe an exact trigger, threshold, debounce, hysteresis, gap, cadence, or duration edit. |
| **Medium** | **Halo3000x Socket** | Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. |
| **Medium** | **SenseCap D1** | **Troubleshoot Network Route.** The "No route to host" error indicates a network-level connectivity issue between the hub and the device. |
| **Low** | **Fan Switch** | Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. |'''


def test_01673_full_01672_live_fixture_closes_remaining_language_gaps() -> None:
    corrected, changed = guard_live_performance_semantics(
        LIVE_01672,
        _performance_evidence(),
    )

    assert changed is True

    for unsafe in (
        "well within healthy limits",
        "Performance Bottlenecks",
        "Blocking Device Execution",
        "does not establish that it; this is a measured performance concern",
        "creates CPU spikes",
        "UI stuttering or delayed automation triggers",
        "adding constant background overhead",
        "suggests the hub is timing out",
        "struggling to reach the TV",
        "connectivity issue between the hub and the device",
    ):
        assert unsafe not in corrected

    assert "**Database:** 188 MB" in corrected
    assert "does not establish a normal-size threshold" in corrected
    assert "a healthy-size threshold" in corrected
    assert "#### ⚠️ Performance Outliers" in corrected
    assert "**1. High-Latency Device Execution**" in corrected
    assert "does not establish material CPU load" in corrected
    assert "a CPU spike" in corrected
    assert "does not establish that it adds material hub overhead" in corrected
    assert "does not establish whether a network timeout" in corrected
    assert "routing/connectivity failure to the configured endpoint" in corrected

    # Measured facts survive deterministic language repair.
    for measured in ("~1,016MB", "46.5°C", "3,041ms", "2,801ms", "6,783 calls", "11.4%", "5,352 calls"):
        assert measured in corrected

    table_lines = [line for line in corrected.splitlines() if line.strip().startswith("|")]
    assert len(table_lines) == 7
    assert table_lines[0] == "| Priority | Target | Action |"
    assert table_lines[1] == "| :--- | :--- | :--- |"
    assert all(line.count("|") == 4 for line in table_lines)
    assert any("**LG webOS TV**" in line for line in table_lines)
    assert any("**Scheduled Jobs**" in line for line in table_lines)
    assert any("**SenseCap D1**" in line for line in table_lines)


def test_01673_scheduler_cross_sentence_variant_is_fail_closed() -> None:
    message = (
        "Executing this many tasks on the exact same second creates CPU spikes "
        "that can lead to UI stuttering or delayed automation triggers."
    )
    corrected, changed = guard_live_performance_semantics(message, _performance_evidence())
    assert changed is True
    assert "creates CPU spikes" not in corrected
    assert "does not establish material CPU load" in corrected
    assert "a CPU spike" in corrected


def test_01673_latency_suggestion_stays_hypothesis_free() -> None:
    message = (
        "The 3-second average execution time suggests the hub is timing out or "
        "struggling to reach the TV."
    )
    corrected, changed = guard_live_performance_semantics(message, _performance_evidence())
    assert changed is True
    assert "suggests the hub is timing out" not in corrected
    assert "does not establish whether a network timeout" in corrected
