from __future__ import annotations

import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from final_answer_coordinator import (  # noqa: E402
    FinalAnswerCoordinator,
    _performance_evidence_only_messages,
)
from performance_evidence_first import (  # noqa: E402
    build_performance_synthesis_contract,
    guard_evidence_first_performance,
)
from synthesis_validator import validate_synthesis  # noqa: E402


def _receipt(sub_tool: str, *, kind: str = "tool_result") -> dict:
    return {
        "tool": "hub_manage_logs",
        "sub_tool": sub_tool,
        "success": True,
        "supports_live_claim": True,
        "evidence_kind": kind,
        "arguments": {"tool": sub_tool},
        "summary": "successful read",
    }


def _performance_evidence() -> list[dict]:
    return [
        _receipt("hub_get_metrics"),
        _receipt("hub_get_performance_stats"),
        _receipt("hub_get_jobs"),
        _receipt("hub_get_logs", kind="performance_api_recent_logs"),
    ]


LIVE_01674 = '''### Hubitat Performance Analysis

The hub is currently stable with healthy core resources, but there are significant inefficiencies in device execution and job scheduling that may cause intermittent latency.

#### 🟢 System Health
*   **Resources:** The hub has **~963MB of free memory** and an internal temperature of **46.1°C**.
*   **Database:** 188 MB. The current turn does not establish a normal-size threshold, a healthy-size threshold, or performance impact from database size alone.
*   **Stability:** No active health alerts are present. The hub is not in safe mode, and there are no reports of high load or low memory.

#### ⚠️ Performance Outliers

**1. High-Latency Device (Blocking Risk)**
The **LG webOS TV** is a major outlier with an average execution time of **3,043.54ms**.
*   **Impact:** An average execution time of over 3 seconds is exceptionally high. If the driver performs synchronous (blocking) network calls, this can cause the hub to "stutter" or delay other automations during execution.

**2. Job Synchronization ("Thunder-Claps")**
Many scheduled tasks share the same scheduled second.
*   **Observation:** At **16:25:00 BST**, the hub is scheduled to execute a massive volume of jobs simultaneously. This includes:
    *   Dozens of `sessionTick` jobs for "Block" devices.
    *   `autoPoll` jobs for the Eufy Robovac socket, Nest Mini socket, and Computer.
This is a measured performance concern, but the current statistics do not establish that it causes hub lag, stutter, congestion, or instability.

**3. High-Frequency Reporting (Chatter)**
Two devices are contributing disproportionately to the hub's processing load:
*   **Fan Switch (Tuya Local):** 5,900 calls (11.3% busy).
*   **Matter Halo3000x Liv Socket:** 7,361 calls (5.5% busy).
*   **Impact:** Constant high-frequency reporting increases background overhead and fills event logs, which can slow down history lookups.

---

### 🛠️ Recommended Improvements

| Priority | Target | Action |
| :--- | :--- | :--- |
| **High** | **Scheduled Jobs** | Review the observed job alignment. Inspect the responsible app configuration before changing scheduled offsets; the current job evidence does not establish that offsetting is configurable, necessary, behaviour-preserving, or performance-improving; the same applies to shifting or staggering. |
| **High** | **LG webOS TV** | Inspect the cited integration implementation/configuration first. The measured latency can justify investigation, but this turn did not read the relevant driver/app code or settings needed to prescribe async/sync, timeout, retry, reconnect, or blocking-model changes. |
| **Medium** | **Tuya/Matter Sockets** | Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. |
| **Low** | **General Cleanup** | The hub is otherwise very healthy. No immediate need for memory management or database optimization. |'''


def test_01675_full_01674_live_fixture_is_evidence_first() -> None:
    corrected, changed = guard_evidence_first_performance(LIVE_01674)
    assert changed is True

    for unsafe in (
        "stable with healthy core resources",
        "significant inefficiencies",
        "may cause intermittent latency",
        "Blocking Risk",
        "major outlier",
        "exceptionally high",
        "If the driver performs synchronous",
        'cause the hub to "stutter"',
        "Thunder-Claps",
        "massive volume of jobs",
        "contributing disproportionately",
        "increases background overhead",
        "fills event logs",
        "slow down history lookups",
        "otherwise very healthy",
        "No immediate need for memory management",
    ):
        assert unsafe not in corrected

    assert "No active core-resource health alerts are reported in this turn" in corrected
    assert "does not establish synchronous blocking" in corrected
    assert "Job Scheduling Alignment" in corrected
    assert "many jobs" in corrected
    assert "comparatively high returned call counts and busy percentages" in corrected
    assert "does not establish material background overhead, log growth, or slower history lookups" in corrected
    assert "does not establish a need for or against memory/database optimisation" in corrected

    for measured in (
        "~963MB",
        "46.1°C",
        "188 MB",
        "3,043.54ms",
        "5,900 calls",
        "11.3%",
        "7,361 calls",
        "5.5%",
    ):
        assert measured in corrected

    table_lines = [line for line in corrected.splitlines() if line.strip().startswith("|")]
    assert len(table_lines) == 6
    assert table_lines[0] == "| Priority | Target | Action |"
    assert table_lines[1] == "| :--- | :--- | :--- |"
    assert all(line.count("|") == 4 for line in table_lines)


def test_01675_validator_adds_evidence_first_issue() -> None:
    corrected, issues = validate_synthesis(LIVE_01674, _performance_evidence())
    assert "performance_evidence_first" in issues
    assert "Blocking Risk" not in corrected
    assert "fills event logs" not in corrected


def test_01675_contract_forbids_unobserved_mechanisms_without_config() -> None:
    contract = build_performance_synthesis_contract(_performance_evidence())
    assert "There is no trusted assistant draft" in contract
    assert "Do not introduce those mechanisms even conditionally" in contract
    assert "No configuration or implementation source was read" in contract
    assert "inspection-first" in contract
    assert "Do not say optimisation is unnecessary" in contract


def test_01675_performance_context_drops_prose_draft_but_keeps_tool_envelope() -> None:
    messages = [
        {"role": "user", "content": "Analyse performance."},
        {"role": "assistant", "content": "UNTRUSTED DRAFT: blocking risk"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "hub_manage_logs", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": "{}"},
    ]
    filtered = _performance_evidence_only_messages(messages)
    assert not any(message.get("content") == "UNTRUSTED DRAFT: blocking risk" for message in filtered)
    assert any(message.get("tool_calls") for message in filtered if message.get("role") == "assistant")
    assert any(message.get("role") == "tool" for message in filtered)


@pytest.mark.asyncio
async def test_01675_final_synthesis_never_sees_original_prose_draft() -> None:
    seen: list[list[dict]] = []

    async def chat(messages: list[dict], tools: list[dict]) -> dict:
        seen.append(messages)
        return {
            "content": (
                "Performance statistics contain a measured execution-time outlier. "
                "Inspect the relevant integration configuration to determine the mechanism."
            )
        }

    evidence = _performance_evidence()
    coordinator = FinalAnswerCoordinator(chat, lambda: evidence)
    answer = await coordinator.answer(
        [
            {"role": "user", "content": "Analyse my Hubitat performance and recommend improvements."},
            {
                "role": "assistant",
                "content": "UNTRUSTED ORIGINAL DRAFT: synchronous blocking causes stutter and CPU spikes.",
            },
            {
                "role": "user",
                "content": "HOST CURRENT-TURN PERFORMANCE SOURCE: hub_get_performance_stats\n{\"avgMs\":3043.54}",
            },
        ]
    )

    assert seen
    flattened = "\n".join(str(message.get("content") or "") for message in seen[0])
    assert "UNTRUSTED ORIGINAL DRAFT" not in flattened
    assert "HOST PERFORMANCE EVIDENCE-FIRST CONTRACT" in flattened
    assert "There is no trusted assistant draft" in flattened
    assert "measured execution-time outlier" in answer
