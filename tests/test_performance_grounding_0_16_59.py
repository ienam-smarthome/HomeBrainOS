from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from api_response_builder import build_agent_response  # noqa: E402
from grounding_policy import GroundingAction, GroundingPolicy  # noqa: E402
from performance_semantic_grounding import ground_performance_semantics  # noqa: E402


def _performance_evidence() -> list[dict[str, object]]:
    return [
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_metrics", "success": True},
        {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_performance_stats", "success": True},
        {"tool": "hub_manage_logs", "sub_tool": "hub_get_logs", "success": True},
    ]


def test_hub_manage_logs_hub_get_logs_satisfies_log_grounding() -> None:
    policy = GroundingPolicy.default(logs_requested=True, conversational=False)
    arguments = {"tool": "hub_get_logs", "args": {"since": "30m", "limit": 100}}

    assert policy.is_live_log_call("hub_manage_logs", arguments) is True
    policy.record_tool_outcome("hub_manage_logs", arguments, success=True)

    decision = policy.decide_no_tool_calls(has_live_evidence=True)
    assert decision.action is GroundingAction.ACCEPT
    assert policy.logs_checked is True


def test_direct_hub_get_logs_also_satisfies_log_grounding() -> None:
    policy = GroundingPolicy.default(logs_requested=True, conversational=False)
    policy.record_tool_outcome("hub_get_logs", {"since": "30m"}, success=True)
    assert policy.decide_no_tool_calls(has_live_evidence=True).action is GroundingAction.ACCEPT


def test_false_no_performance_data_answer_is_corrected_at_serialization() -> None:
    outcome = SimpleNamespace(
        message=(
            "The current-turn evidence does not provide the necessary data to analyze hub performance, "
            "review logs, or recommend improvements. No metrics, performance statistics, or log entries "
            "were returned in the provided results."
        ),
        route="unified-mcp-agent",
        request_class="live-read",
        evidence=_performance_evidence(),
        metrics={"outcome": "success", "counters": {"model_rounds": 5}},
        choices=[],
        confirmation_required=False,
        confirmation_count=0,
        automation_items=[],
    )

    response = build_agent_response(
        outcome,
        model="gemma4:31b",
        elapsed_ms=100,
        version="0.16.59",
    )
    message = response["message"]
    assert "does not provide the necessary data" not in message
    assert "No metrics, performance statistics, or log entries were returned" not in message
    assert "successful hub metrics, performance statistics and logs" in message


def test_live_01658_performance_wording_is_structurally_grounded() -> None:
    draft = '''### ⚠️ Performance Bottlenecks (Measured)

**1. Critical Execution Delay: LG webOS TV**
* **Finding:** This device has an average execution time of **3,084ms (over 3 seconds)**.
* **Impact:** In Hubitat, long execution times like this are typically "blocking" calls. When this driver runs, it can pause other hub activities, leading to perceived lag in your automations.

### 🛠️ Recommended Improvements

1. **Optimize the LG webOS TV Driver:**
   * **Hypothesis:** The 3-second delay is likely caused by a network timeout or a synchronous HTTP request to the TV.
   * **Action:** Check the driver settings for any "polling" intervals and increase them. If you are using a community driver, check for updates or a "non-blocking" version.
2. **Audit SenseCap D1 Settings:**
Inspect the cited integration/device configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact polling/reporting threshold, interval, or frequency. Inspect the cited component configuration first. Recent activity can justify a tuning review, but this turn did not read the relevant settings needed to prescribe an exact configuration change.
3. **Review MCP Rule Server & Watchtower:**
   * **Action:** Since these have execution times nearing 1 second, check if they are performing complex loops or external API calls. Ensure they aren't triggered by the chatty devices mentioned above.
'''

    corrected = ground_performance_semantics(draft)
    assert "3,084ms" in corrected
    assert 'typically "blocking" calls' not in corrected
    assert "pause other hub activities" not in corrected
    assert "likely caused by a network timeout" not in corrected
    assert '"polling" intervals and increase them' not in corrected
    assert '"non-blocking" version' not in corrected
    assert "complex loops or external API calls" not in corrected
    assert "Ensure they aren't triggered" not in corrected
    sensecap_line = next(
        line for line in corrected.splitlines() if line.startswith("Inspect the cited")
    )
    assert sensecap_line.count("Inspect the cited") == 1


def test_recommended_improvements_is_an_action_heading() -> None:
    draft = '''### 🛠️ Recommended Improvements
| Component | Action | Expected Impact |
| :--- | :--- | :--- |
| LG | Check the driver settings for any "polling" intervals and increase them. | Lower lag |
'''
    corrected = ground_performance_semantics(draft)
    assert "| LG | Inspect the cited integration/device configuration first." in corrected
    assert "increase them" not in corrected
