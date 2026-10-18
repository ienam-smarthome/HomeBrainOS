"""v0.18.33: device command vocabulary is not user write authorization."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from mcp_agent_orchestrator import _explicit_mutation_request, UnifiedMCPAgent
from request_outcome_policy import classify_completed_request
from api_response_builder import build_agent_response
from request_metrics import RequestMetrics

EXPLAIN = (
    "Explain the difference between a Hubitat switch=off state event, a "
    "command-off event, an automation execution log and physical device "
    "acknowledgement. Which evidence is available for Bedroom 3 Mesh on "
    "12 October 2026? Identify what remains unverified. Read-only."
)


@pytest.mark.parametrize("prompt", [
    EXPLAIN,
    "Explain a switch=off and command-off event. Read-only.",
    "Compare OFF and ON command history without changing anything.",
    "Distinguish a recorded command from a state change.",
    "Describe why the switch went off; do not change any device.",
    "Review the previous off command and explain its provenance.",
    "Investigate whether switch=off means command-off.",
    "Verify whether app 3950 issued OFF at 01:30. Read-only.",
])
def test_explanations_or_historical_reads_are_not_user_authorized_writes(prompt):
    assert _explicit_mutation_request(prompt) is False


@pytest.mark.parametrize("prompt", [
    "Turn off Bedroom 3 Mesh.",
    "Please disable app 3950.",
    "Explain switch=off. Then turn off Bedroom 3 Mesh.",
    "Compare command history and then restart the hub.",
    "Verify whether app 3950 issued OFF. Then disable app 3950.",
    "Review current switch history and change the plug name.",
])
def test_commands_and_mixed_requests_preserve_write_confirmation_path(prompt):
    assert _explicit_mutation_request(prompt) is True


@pytest.mark.asyncio
async def test_real_explanation_intent_is_classed_as_live_read_not_failed_write(monkeypatch):
    async def read_stub(self, prompt, conversation_history=None, *, session_id="default"):
        assert not self._mutation_requested_by_user.get()
        self.evidence.record(
            "hub_read_devices",
            {"tool": "hub_list_device_events", "args": {
                "deviceId": "7103", "attribute": "switch", "hoursBack": 168,
            }},
            success=True, elapsed_ms=1, summary="historical state read",
            effect="read", mutates=False,
        )
        return "Hubitat recorded switch=off; command dispatch not verified."

    monkeypatch.setattr(UnifiedMCPAgent, "_process_user_request", read_stub)

    class MCP: pass
    agent = UnifiedMCPAgent(MCP(), "test", ai_client=object())
    outcome = await agent.process_user_request_result(
        EXPLAIN, session_id="free-interpretation-01833",
    )
    assert outcome.request_class == "live-read"
    assert "command dispatch not verified" in outcome.message
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0]["mutates"] is False


def test_incomplete_task_evidence_never_displays_positive_success():
    assert classify_completed_request({"task_evidence_incomplete": 1}) == "unresolved"
    assert classify_completed_request({
        "task_evidence_incomplete": 1, "device_control_failures": 1,
    }) == "failed"
    assert classify_completed_request({"task_evidence_incomplete": 0}) == "success"


def test_free_gemma_model_reports_ollama_free_allowance_not_anthropic_charges():
    outcome = SimpleNamespace(
        route="unified-mcp-agent",
        request_class="live-read",
        message="Recorded state; command actor unverified.",
        choices=[], evidence=[], confirmation_required=False,
        confirmation_count=0, investigation_coverage=None,
        metrics={
            "outcome": "unresolved", "counters": {},
            "timings_ms": {},
            "model_round_details": [
                {"model": "gemma4:31b", "provider": "ollama-cloud"}
                for _ in range(8)
            ],
        },
    )
    result = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=46929, version="0.18.33",
    )
    usage = result["model_usage"]
    assert usage["free_rounds"] == 8
    assert usage["paid_rounds"] == 0
    assert usage["paid_used"] is False
    assert usage["charges_controlled_by"] == "ollama-free-allowance"


def test_block_counter_is_registered_in_public_technical_metrics():
    metrics = RequestMetrics()
    token = metrics.begin()
    try:
        metrics.increment("read_only_model_write_blocked")
        result = metrics.finish(metrics.completed_outcome())
        assert result["counters"]["read_only_model_write_blocked"] == 1
    finally:
        metrics.reset(token)
