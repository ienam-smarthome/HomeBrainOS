from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from performance_semantic_grounding import ground_performance_semantics  # noqa: E402


def test_summary_table_grounds_recommendation_column_by_header() -> None:
    draft = '''**Summary of Findings:**
| Component | Metric | Status | Recommendation |
| :--- | :--- | :--- | :--- |
| **Memory/DB** | 839MB / 152KB | ✅ Excellent | No action needed. |
| **Scheduler** | 220 Jobs | ⚠️ High | Reduce `sessionTick` and polling frequency. |
| **Tuya Fan** | 19k calls | ⚠️ Chatty | Increase reporting thresholds. |
| **LG TV** | 3.1s avg | ⚠️ Slow | Check network/disable aggressive polling. |
'''

    corrected = ground_performance_semantics(draft)

    assert "839MB / 152KB" in corrected
    assert "220 Jobs" in corrected
    assert "19k calls" in corrected
    assert "3.1s avg" in corrected
    assert "Reduce `sessionTick` and polling frequency" not in corrected
    assert "Increase reporting thresholds" not in corrected
    assert "disable aggressive polling" not in corrected
    assert corrected.count("Inspect the cited integration/device configuration first.") >= 3


def test_conditional_and_gerund_tuning_is_inspection_first() -> None:
    draft = '''### Recommended Improvements
* **Consolidate Polling:** Check the settings for Life360 Connect and Octopus Energy. If they are polling more often than needed, increasing the interval will free up CPU cycles.
* **LG TV Polling:** Given the 3-second execution time, check if the LG TV driver is polling for status too frequently. If possible, switch to a push model or increase the poll interval.
* **Auto Refresh:** Disable auto-refresh or status polling if the driver allows it.
'''

    corrected = ground_performance_semantics(draft)

    assert "increasing the interval" not in corrected
    assert "switch to a push model" not in corrected
    assert "increase the poll interval" not in corrected
    assert "Disable auto-refresh" not in corrected
    assert corrected.count("Inspect the cited integration/device configuration first.") == 3


def test_unproven_impact_language_is_localized_without_losing_measurements() -> None:
    draft = '''### Performance Analysis
* **LG webOS TV:** It has a very high **average execution time (~3.1 seconds)**, which can block other automations from running promptly.
* **Fan Switch:** This device has **19,103 executions**. This high volume contributes to a **14.8% busy rate**.

### Log Observations
The recent logs reveal two primary sources of inefficiency:
* A constant heartbeat can cause micro-stutters in automation execution.
'''

    corrected = ground_performance_semantics(draft)

    assert "~3.1 seconds" in corrected
    assert "19,103 executions" in corrected
    assert "14.8% busy rate" in corrected
    assert "which;" not in corrected
    assert "can block other automations" not in corrected
    assert "contributes to" not in corrected
    assert "primary sources of inefficiency" not in corrected
    assert "can cause micro-stutters" not in corrected


def test_dangling_which_is_removed_when_mechanism_clause_is_localized() -> None:
    draft = "LG webOS TV averages 3,084ms, which can block hub execution threads and cause lag."
    corrected = ground_performance_semantics(draft)

    assert "3,084ms" in corrected
    assert "which;" not in corrected
    assert "which can block" not in corrected
    assert "the implementation cause of that measured load is not established" in corrected


def test_live_01659_recommendation_shapes_are_grounded() -> None:
    draft = '''### **Recommended Improvements**

**Priority 1: Reduce Scheduler Noise (High Impact)**
* **Consolidate Polling:** Check the settings for **Life360 Connect** and **Octopus Energy**. If they are polling more often than you actually need the data, increasing the interval will free up significant CPU cycles.

**Priority 2: Address "Chatty" Devices (Medium Impact)**
* **Fan Switch (Tuya Local):** Increase reporting thresholds.

**Priority 3: Investigate Slow Responses (Low Impact)**
* **LG webOS TV:** The 3-second average execution time is a "blocking" risk. Ensure the TV is on a stable network connection. If the driver allows, disable any "auto-refresh" or "status polling" features that might be timing out.

**Summary of Findings:**
| Component | Metric | Status | Recommendation |
| :--- | :--- | :--- | :--- |
| **Scheduler** | 220 Jobs | ⚠️ High | Reduce `sessionTick` and polling frequency. |
| **Tuya Fan** | 19k calls | ⚠️ Chatty | Increase reporting thresholds. |
| **LG TV** | 3.1s avg | ⚠️ Slow | Check network/disable aggressive polling. |
'''

    corrected = ground_performance_semantics(draft)

    assert "220 Jobs" in corrected
    assert "19k calls" in corrected
    assert "3.1s avg" in corrected
    for unsafe in (
        "increasing the interval",
        "Increase reporting thresholds",
        "disable any \"auto-refresh\"",
        "Reduce `sessionTick` and polling frequency",
        "Check network/disable aggressive polling",
    ):
        assert unsafe not in corrected
