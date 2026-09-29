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
    finalize_performance_api_outcome,
)
from performance_live_semantic_guard import guard_live_performance_semantics  # noqa: E402


def _receipt(tool: str, sub_tool: str) -> dict:
    return {
        "tool": tool,
        "sub_tool": sub_tool,
        "success": True,
        "supports_live_claim": True,
        "evidence_kind": "tool_result",
        "arguments": {"tool": sub_tool},
        "summary": "successful read",
    }


class _Result:
    def __init__(self, data=None, text: str = "") -> None:
        self.data = data
        self.text = text


class _MCP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return _Result(
            data={
                "logs": [
                    {
                        "level": "INFO",
                        "message": "Halo3000x ActivePower is 7.0 W",
                    }
                ],
                "count": 1,
            }
        )


class _Agent:
    def __init__(self) -> None:
        self.messages = []

    @staticmethod
    def _tool_succeeded(result) -> bool:
        return True

    async def _chat(self, messages, tools):
        self.messages.append(messages)
        return {
            "content": (
                "Database: 185 MB. LG webOS TV averaged 3038 ms. "
                "There are 220 scheduled jobs. Recent Halo3000x reports are observations; "
                "the current evidence does not establish that they cause hub lag."
            )
        }


@pytest.mark.asyncio
async def test_api_finalizer_reuses_normalized_original_payloads_without_snapshot_rereads() -> None:
    _consume_packet()
    _append_packet(
        "hub_get_metrics",
        '{"result":{"current":{"freeMemoryMB":982,"databaseSizeMB":185}}}',
    )
    _append_packet(
        "hub_get_performance_stats",
        '{"result":{"snapshot":{"databaseSizeMB":185},"deviceStats":[{"name":"LG webOS TV","avgMs":3038}]}}',
    )
    _append_packet(
        "hub_get_jobs",
        '{"result":{"scheduledJobs":220}}',
    )

    outcome = ObservedAgentOutcome(
        message="provider draft",
        request_class="live-read",
        evidence=[
            _receipt("hub_read_diagnostics", "hub_get_metrics"),
            _receipt("hub_manage_logs", "hub_get_performance_stats"),
            _receipt("hub_manage_logs", "hub_get_jobs"),
        ],
        choices=[],
        metrics={
            "outcome": "success",
            "counters": {"tool_calls": 3, "model_rounds": 2},
            "timings_ms": {},
        },
    )
    agent = _Agent()
    mcp = _MCP()

    result = await finalize_performance_api_outcome(
        agent,
        mcp,
        outcome,
        "Analyse my Hubitat performance and recommend improvements.",
    )

    assert mcp.calls == [
        (
            "hub_manage_logs",
            {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}},
        )
    ]
    assert result.metrics["counters"]["tool_calls"] == 4
    assert "performance_api_snapshot_attempt" not in result.metrics["counters"]
    rendered = "\n".join(
        str(item.get("content") or "")
        for call in agent.messages
        for item in call
        if isinstance(item, dict)
    )
    assert '"databaseSizeMB":185' in rendered
    assert "databaseSizeKB" not in rendered
    assert '"scheduledJobs":220' in rendered


def test_live_guard_repairs_exact_01668_heading_and_halo_corruption() -> None:
    message = '''### ⚠️ Performance Outliers

**1. High-Latency Devices (Blocking Potential)**

**2. Job Volume & Scheduling Overhead**
* **Recurring Overhead:** sessionTick jobs are clustered.
* **Matter Halo3000x Liv Socket:** High call volume (5,711 calls) and a measured 5.8% busy rate. While logs show frequent `ActivePower` reports (approximately every 10 seconds), the current statistics do not establish that this specific activity; this is a measured performance concern, but the current statistics do not establish that it; this is a measured performance concern, but the current statistics do not establish that it causes hub lag, stutter, congestion, or instability.
* **Microwave (MQTT):** Highest overall call volume (19,978 calls), though its low average execution time (4.35ms) means it is not currently a bottleneck.'''

    corrected, changed = guard_live_performance_semantics(
        message,
        [_receipt("hub_manage_logs", "hub_get_performance_stats")],
    )

    assert changed is True
    assert "Blocking Potential" not in corrected
    assert "Scheduling Overhead" not in corrected
    assert "Recurring Overhead" not in corrected
    assert corrected.casefold().count("this is a measured performance concern") <= 1
    assert "does not establish that it;" not in corrected
    assert "does not establish that this specific activity;" not in corrected
    assert "not currently a bottleneck" not in corrected
    assert "does not establish either a performance problem or the absence of one" in corrected
