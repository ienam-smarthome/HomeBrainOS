"""Historical rule command execution must not finish via config-only fast path.

v0.18.24 live: the Oct 12 01:30 OFF execution-verification question
returned after 368 ms, no model, a single hub_get_app_config with
includeSettings=false and irrelevant retained illuminance/motion advice.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from rule_machine_analysis import (
    parse_rule_analysis_request, historical_rule_execution_request,
)
from adaptive_investigation_policy import model_led_investigation_request
from homebrain_agent import UnifiedMCPAgent
from mcp_agent_orchestrator import (
    UnifiedMCPAgent as BaseUnifiedMCPAgent, AgentOutcome,
    _explicit_mutation_request,
)


QUESTION = (
    'Verify whether the automation "Power saving: Bedroom 3 Mesh off @night" '
    "(app 3950) actually issued an OFF command to Bedroom 3 Mesh "
    "(device 7103) on 12 October 2026 at approximately 01:30 BST. "
    "Check original device events and automation execution evidence. "
    "Distinguish a recorded command from successful device acknowledgement. "
    "Do not infer execution from configuration or truncated history. Read-only."
)


def test_actual_v01824_request_requires_historical_provenance_not_rule_snapshot():
    assert historical_rule_execution_request(QUESTION)
    assert parse_rule_analysis_request(QUESTION) is None
    assert not _explicit_mutation_request(QUESTION)
    # The known regression: generic router misses "Verify whether ... issued".
    assert not model_led_investigation_request(QUESTION)


@pytest.mark.parametrize("question", [
    "Check whether app 3950 issued an OFF command yesterday.",
    "Verify appId 3950 execution logs near 01:30.",
    "Did rule 3950 actually run at 01:30?",
    "Investigate whether app 3950 sent off() at 01:30.",
    "Reconstruct when automation app 3950 triggered and whether a device acknowledged.",
])
def test_historical_command_questions_bypass_snapshot(question):
    assert historical_rule_execution_request(question)
    assert parse_rule_analysis_request(question) is None


@pytest.mark.parametrize("question", [
    "Review app 3950 current settings.",
    "Inspect Rule Machine app 3950 referenced sensor states.",
    "Analyse rule 3950 condition and required expression.",
])
def test_current_rule_configuration_remains_eligible_for_direct_fast_path(question):
    assert not historical_rule_execution_request(question)
    assert parse_rule_analysis_request(question) == ("3950", None)


def test_non_app_events_and_explicit_write_do_not_activate_read_override():
    assert not historical_rule_execution_request(
        "Verify whether Bedroom 3 Mesh switched OFF yesterday."
    )
    assert _explicit_mutation_request(
        "Please disable app 3950 and delete the rule."
    )
    assert _explicit_mutation_request(
        "Verify whether app 3950 issued OFF yesterday. Then disable app 3950."
    )
    assert _explicit_mutation_request(
        "Check if app 3950 executed and then turn off device 7103."
    )


class NoReadMCP:
    def __init__(self):
        self.calls = []

    async def call_tool(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("config-only Rule Machine snapshot must not run")


@pytest.mark.asyncio
async def test_named_app_historical_query_enters_model_evidence_route(monkeypatch):
    called = []

    async def expected_model_path(self, user_prompt, conversation_history=None,
                                  *, session_id="default"):
        called.append((user_prompt, session_id))
        return AgentOutcome(
            message="Model-led historical read path selected (test stub).",
            request_class="live-read", evidence=[], choices=[],
        )

    monkeypatch.setattr(
        BaseUnifiedMCPAgent, "process_user_request_result",
        expected_model_path,
    )
    mcp = NoReadMCP()
    agent = UnifiedMCPAgent(mcp, "key")
    answer = await agent.process_user_request_result(
        QUESTION, session_id="historical-app-3950-routing-test",
    )
    assert len(called) == 1
    assert called[0] == (QUESTION, "historical-app-3950-routing-test")
    assert not mcp.calls
    assert answer.metrics["counters"]["historical_rule_execution_routed"] == 1
    assert answer.metrics["counters"]["investigation_snapshot_shortcut_bypassed"] == 1
    assert answer.metrics["counters"].get("rule_analysis_partial", 0) == 0
    assert "Model-led historical read path" in answer.message
