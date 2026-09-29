from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from observed_agent_outcome import ObservedAgentOutcome  # noqa: E402
from performance_api_finalizer import (  # noqa: E402
    _append_packet,
    _consume_packet,
    _packet_map,
    _repair_metric_denial,
    finalize_performance_api_outcome,
)


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


LIVE_01671 = '''### Hubitat Performance Analysis

Based on the current system jobs and logs, the following performance bottlenecks have been identified:

#### ⚠️ Critical Performance Issues

**1. Job Synchronization ("Thunder-Claps")**
There is a severe synchronization of scheduled tasks occurring at the top of the minute.
*   **Observation:** At **14:29:00 BST**, the hub is scheduled to execute over 30 jobs simultaneously, including a large cluster of `sessionTick` jobs for "Block [Device]" and `autoPoll` jobs.
*   **Observation:** A second cluster occurs at **14:30:00 BST**, involving system cleanup, Matter node checks, and several app refreshes.
This is a measured performance concern, but the current statistics do not establish that it causes hub lag, stutter, congestion, or instability.

**2. High-Frequency App Triggering**
The logs indicate an efficiency issue with the **"Washing machine finished notification" (app 4157)**.
*   **Observation:** This app triggered three times within approximately three seconds, reacting to power reports from the "Washing Machine (MQTT)" device.
This is a measured performance concern, but the current statistics do not establish that it causes hub lag, stutter, congestion, or instability.

**3. Device Chatter**
*   **Observation:** The **Halo3000x socket power** is reporting updates frequently. While not as extreme as the app triggering, constant reporting adds to the background load.

---

### 🛠️ Recommended Improvements

| Priority | Target | Action |
| :--- | :--- | :--- |
| **High** | **Scheduled Jobs** | **Stagger the "Block" Ticks.** The high volume of `sessionTick` jobs at `:00` seconds should be offset. Inspect the app responsible for the scheduled jobs before changing their alignment; the current job evidence does not establish that staggering is configurable, necessary, or behaviour-preserving. |
| **High** | **Washing Machine App** | Inspect the cited automation configuration first. Recent activity can justify an execution review, but this turn did not read the rule/app configuration needed to prescribe an exact trigger, threshold, debounce, hysteresis, gap, cadence, or duration edit. |
| **Medium** | **Halo3000x Socket** | Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. |
| **Medium** | **Top-of-Hour Jobs** | **Shift System Tasks.** Move the 14:30:00 cluster (Calendar, Meter, and System Cleanup) to different offsets (e.g., `:15`, `:30`, or `:45`) to flatten the load curve. |

**Note on Missing Data:** The available evidence does not establish current memory usage, internal temperature, database size, or specific execution times for individual devices (such as the LG TV).'''


class _MCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        raise AssertionError("0.16.72 fixture should reuse existing four-tool evidence")


class _Agent:
    def __init__(self, content: str) -> None:
        self.content = content
        self.messages: list[list[dict]] = []

    @staticmethod
    def _tool_succeeded(result) -> bool:
        return True

    async def _chat(self, messages, tools):
        self.messages.append(messages)
        return {"content": self.content}


def test_packet_budgets_preserve_all_four_source_classes_under_pressure() -> None:
    _consume_packet()
    _append_packet("hub_get_metrics", "m" * 12000)
    _append_packet("hub_get_performance_stats", "p" * 16000)
    _append_packet("hub_get_logs", "l" * 12000)
    _append_packet("hub_get_jobs", "j" * 12000)

    packet = _packet_map(_consume_packet())
    assert set(packet) == {
        "hub_get_metrics",
        "hub_get_performance_stats",
        "hub_get_logs",
        "hub_get_jobs",
    }
    assert len(packet["hub_get_metrics"]) == 7500
    assert len(packet["hub_get_performance_stats"]) == 11500
    assert len(packet["hub_get_jobs"]) == 7500
    assert len(packet["hub_get_logs"]) == 4500


@pytest.mark.asyncio
async def test_01672_full_live_fixture_keeps_metrics_and_repairs_remaining_overreach() -> None:
    _consume_packet()
    _append_packet(
        "hub_get_metrics",
        '{"result":{"current":{"freeMemoryMB":962,"temperatureC":45.3,"databaseSizeMB":198,"safeMode":false},"healthAlerts":[]}}',
    )
    _append_packet(
        "hub_get_performance_stats",
        '{"result":{"deviceStats":[{"name":"LG webOS TV","avgMs":3040}],"appStats":[]}}',
    )
    _append_packet(
        "hub_get_logs",
        '{"result":{"logs":[{"message":"Washing machine finished notification triggered"},{"message":"Halo3000x ActivePower is 7.1 W"}]}}',
    )
    _append_packet(
        "hub_get_jobs",
        '{"result":{"scheduledJobs":219,"rows":[{"name":"sessionTick","next":"14:29:00 BST"}]}}',
    )

    outcome = ObservedAgentOutcome(
        message="provider draft",
        request_class="live-read",
        evidence=[
            _receipt("hub_read_diagnostics", "hub_get_metrics"),
            _receipt("hub_manage_logs", "hub_get_performance_stats"),
            _receipt("hub_manage_logs", "hub_get_logs"),
            _receipt("hub_manage_logs", "hub_get_jobs"),
        ],
        choices=[],
        metrics={
            "outcome": "success",
            "counters": {"tool_calls": 4, "model_rounds": 2},
            "timings_ms": {},
        },
    )
    agent = _Agent(LIVE_01671)
    mcp = _MCP()

    result = await finalize_performance_api_outcome(
        agent,
        mcp,
        outcome,
        "Analyse my Hubitat performance and recommend improvements.",
    )

    assert mcp.calls == []
    assert len(agent.messages) == 1
    assert result.metrics["counters"]["tool_calls"] == 4
    assert result.metrics["counters"]["model_rounds"] == 3
    assert result.metrics["counters"]["performance_api_packet_sources"] == 4
    assert result.metrics["counters"]["performance_api_metrics_payload_reused"] == 1
    assert result.metrics["counters"]["performance_api_metric_denial_repair"] == 1
    assert "performance_api_metrics_payload_missing" not in result.metrics["counters"]

    message = result.message
    for unsafe in (
        "performance bottlenecks have been identified",
        "Critical Performance Issues",
        "severe synchronization of scheduled tasks",
        "scheduled to execute over 30 jobs simultaneously",
        "efficiency issue",
        "constant reporting adds to the background load",
        'Stagger the "Block" Ticks',
        "should be offset",
        "Shift System Tasks",
        "Move the 14:30:00 cluster",
        "available evidence does not establish current memory usage",
    ):
        assert unsafe not in message

    assert "performance observations and outliers were identified" in message
    assert "scheduled for the same second" in message
    assert "does not establish material background load" in message
    assert "does not establish that offsetting is configurable" in message
    assert "alternate offsets are configurable" in message
    assert "**Current metrics:** free memory 962 MB; internal temperature 45.3°C; database 198 MB." in message

    table_lines = [line for line in message.splitlines() if line.strip().startswith("|")]
    assert len(table_lines) == 6
    assert table_lines[0] == "| Priority | Target | Action |"
    assert table_lines[1] == "| :--- | :--- | :--- |"
    assert all(line.count("|") == 4 for line in table_lines)
    assert any("Review the \"Block\" tick alignment" in line for line in table_lines)
    assert any("Review system-task timing" in line for line in table_lines)


def test_metric_denial_reports_context_limitation_when_payload_is_missing() -> None:
    message = (
        "**Note on Missing Data:** The available evidence does not establish current memory usage, "
        "internal temperature, database size, or individual execution times."
    )
    repaired, changed = _repair_metric_denial(
        message,
        metrics_content="",
        metrics_succeeded=True,
    )
    assert changed is True
    assert "hub_get_metrics` succeeded" in repaired
    assert "synthesis-context limitation" in repaired
    assert "hub lacks those metrics" not in repaired
