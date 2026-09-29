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


LIVE_01673 = '''### Hubitat Performance Analysis

The hub is currently in a healthy state regarding core resources, but there are significant inefficiencies in device latency and job scheduling that could lead to intermittent performance degradation.

#### 🟢 System Health
*   **Resources:** The hub has **~970MB of free memory** and an internal temperature of **47.7°C**.
*   **Database:** 188 MB. The current turn does not establish a normal-size threshold, a healthy-size threshold, or performance impact from database size alone.
*   **Stability:** No active health alerts are present; the hub is not in safe mode, and there are no reports of severe load or low memory.

#### ⚠️ Performance Outliers

**1. High-Latency Devices**
This is an implementation hypothesis worth investigating; the current performance statistics do not establish whether timeouts, API latency, polling/config pushes, retries, reconnects, reporting cadence, blocking calls, or another implementation mechanism is responsible.
*   **LG webOS TV:** Average execution time of **3,042.69ms**.
*   **OpenWeatherMap Multi-API:** Average execution time of **2,694.13ms**.

**2. Job Synchronization ("Thunder-Claps")**
There is a severe clustering of scheduled tasks occurring at the exact same second.
*   **Observation:** At **15:39:00 BST**, a massive block of jobs is scheduled simultaneously. This includes numerous `sessionTick` jobs for "Block" devices (e.g., *Phone-Runa-Pixel-9a*, *Tab-S9-FE*, *Home-Assistant*) and `autoPoll` jobs for the *Eufy Robovac socket*, *Nest Mini socket*, and *Computer*.
This is a measured performance concern, but the current statistics do not establish that it causes hub lag, stutter, congestion, or instability.

**3. High-Frequency Reporting (Chatter)**
Several devices and apps are consuming a disproportionate amount of processing time:
*   **Devices:** The **Fan Switch (Tuya Local)** is 11.5% busy (5,595 calls), and the **Matter Halo3000x Liv Socket** is 5.6% busy (7,038 calls).
*   **Apps:** The **MCP Rule Server** is the most resource-intensive app, accounting for **27.7%** of the hub's busy time.

---

### 🛠️ Recommended Improvements

| Priority | Target | Action |
| :--- | :--- | :--- |
| **High** | **LG webOS TV** | Inspect the cited integration implementation/configuration first. The measured latency can justify investigation, but this turn did not read the relevant driver/app code or settings needed to prescribe async/sync, timeout, retry, reconnect, or blocking-model changes. |
| **High** | **Scheduled Jobs** | Review the "Block" tick alignment. Shift the `sessionTick` and `autoPoll` jobs away from the `:00` second mark. Offsetting these by a few seconds each will flatten the CPU load curve. |
| **Medium** | **Halo3000x & Fan Switch** | Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. |
| **Medium** | **MCP Rule Server** | **Optimize Logic.** Given it consumes 27.7% of the hub's busy time, review the rules within this server for inefficient loops or overly frequent triggers. |
| **Low** | **OpenWeatherMap** | Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. |'''


def test_01674_full_01673_live_fixture_closes_generic_recommendation_gaps() -> None:
    corrected, changed = guard_live_performance_semantics(
        LIVE_01673,
        _performance_evidence(),
    )

    assert changed is True

    for unsafe in (
        "significant inefficiencies",
        "could lead to intermittent performance degradation",
        "severe clustering",
        "massive block of jobs",
        "disproportionate amount of processing time",
        "most resource-intensive app",
        "Shift the `sessionTick` and `autoPoll` jobs away",
        "flatten the CPU load curve",
        "Optimize Logic",
        "for inefficient loops or overly frequent triggers",
        "overly frequent triggers",
    ):
        assert unsafe not in corrected

    assert "Current resource readings show no active core-resource health alerts" in corrected
    assert "Many scheduled tasks share the same scheduled second" in corrected
    assert "many jobs are scheduled for the same second" in corrected
    assert "comparatively high busy percentages" in corrected
    assert "highest returned app busy percentage" in corrected
    assert "does not establish that offsetting is configurable" in corrected
    assert "same applies to shifting or staggering" in corrected
    assert "does not establish inefficient loops, trigger frequency" in corrected

    for measured in (
        "~970MB",
        "47.7°C",
        "188 MB",
        "3,042.69ms",
        "2,694.13ms",
        "11.5%",
        "5,595 calls",
        "5.6%",
        "7,038 calls",
        "27.7%",
    ):
        assert measured in corrected

    table_lines = [line for line in corrected.splitlines() if line.strip().startswith("|")]
    assert len(table_lines) == 7
    assert table_lines[0] == "| Priority | Target | Action |"
    assert table_lines[1] == "| :--- | :--- | :--- |"
    assert all(line.count("|") == 4 for line in table_lines)
    assert any("**Scheduled Jobs**" in line for line in table_lines)
    assert any("**MCP Rule Server**" in line for line in table_lines)


def test_01674_generic_scheduler_offsets_require_configuration_evidence() -> None:
    message = (
        "Shift the sessionTick and autoPoll jobs away from the :00 mark. "
        "Offsetting these by a few seconds will flatten the CPU load curve."
    )
    corrected, changed = guard_live_performance_semantics(message, _performance_evidence())
    assert changed is True
    assert "Shift the sessionTick" not in corrected
    assert "flatten the CPU load curve" not in corrected
    assert "does not establish that offsetting is configurable" in corrected
    assert "performance-improving" in corrected


def test_01674_busy_percentage_does_not_invent_implementation_mechanism() -> None:
    message = (
        "**Optimize Logic.** Given it consumes 27.7% of the hub's busy time, review the rules "
        "for inefficient loops or overly frequent triggers."
    )
    corrected, changed = guard_live_performance_semantics(message, _performance_evidence())
    assert changed is True
    assert "Optimize Logic" not in corrected
    assert "for inefficient loops or overly frequent triggers" not in corrected
    assert "overly frequent triggers" not in corrected
    assert "27.7%" not in corrected or "busy percentage" in corrected
    assert "does not establish inefficient loops, trigger frequency" in corrected
