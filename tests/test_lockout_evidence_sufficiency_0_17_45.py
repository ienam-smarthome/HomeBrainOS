"""0.17.45: skip exploratory model rounds only with corroborated lockout evidence.

No Hubitat connections or writes. Test both the evidence gate and the real
orchestrator dispatch boundary using an in-memory host prefetch.
"""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from motion_lockout_investigation import collected_lockout_ready_for_synthesis
from mcp_agent_orchestrator import UnifiedMCPAgent
from request_metrics import RequestMetrics
import mcp_agent_orchestrator as orchestrator


QUESTION = (
    "Investigate the latest manual OFF of Livingroom Light 1 followed by "
    "motion. Did app 4019's three-minute motion lockout engage? Read-only."
)


def complete_details():
    return {
        "status": "partial-focal-sequence",
        "appId": "4019", "lightDeviceId": "7805",
        "manualOffVerified": True,
        "focalOff": "2026-10-12T22:49:27.529000+00:00",
        "focalSelection": {
            "selectedOff": "2026-10-12T22:49:27.529000+00:00",
            "latestObservedOff": "2026-10-13T07:43:44.028000+00:00",
            "manualOffVerified": True,
        },
        "currentConfiguration": {
            "settingsRead": True, "configuredDurationMinutes": 300,
            "notHistoricalConfigurationProof": True,
        },
        "lockoutExecutionVerified": False,
        "lockoutFailureVerified": False,
        "sources": [
            {"source": "bounded-light-device-history", "success": True},
            {"source": "targeted-native-controller-history",
             "readSucceeded": True, "verifiedPhysicalPresses": 1},
            {"source": "present-day-app-configuration", "available": True,
             "historicalExecutionProven": False},
            {"source": "bounded-app-execution-logs",
             "readSucceeded": True, "returnedRows": 0,
             "emptyDoesNotProveNoExecution": True},
        ],
    }


def receipt(details=None, *, success=True):
    return {
        "tool": "homebrain_motion_lockout_investigation",
        "success": success,
        "details": details if details is not None else complete_details(),
    }


def test_completed_evidence_skips_exploration_without_asserting_lockout():
    evidence = complete_details()
    assert evidence["lockoutExecutionVerified"] is False
    assert collected_lockout_ready_for_synthesis(QUESTION, [receipt(evidence)])
    assert "lockout_prefetch_sufficiency_stop" in RequestMetrics.ALLOWED_COUNTERS


@pytest.mark.parametrize("broken", [
    ("manualOffVerified", False),
    ("focalOff", "2026-10-13T07:43:44+00:00"),
    ("appId", ""),
    ("lightDeviceId", ""),
    ("status", "no-focal-off-observed"),
])
def test_missing_focal_proof_stays_in_investigation(broken):
    evidence = complete_details()
    evidence[broken[0]] = broken[1]
    assert not collected_lockout_ready_for_synthesis(
        QUESTION, [receipt(evidence)]
    )


@pytest.mark.parametrize("source", [
    "bounded-light-device-history",
    "targeted-native-controller-history",
    "present-day-app-configuration",
    "bounded-app-execution-logs",
])
def test_missing_authoritative_source_prevents_shortcut(source):
    evidence = complete_details()
    evidence["sources"] = [
        item for item in evidence["sources"] if item["source"] != source
    ]
    assert not collected_lockout_ready_for_synthesis(
        QUESTION, [receipt(evidence)]
    )


def test_failed_or_absent_config_and_controller_read_is_not_sufficient():
    facts = complete_details()
    facts["currentConfiguration"]["settingsRead"] = False
    assert not collected_lockout_ready_for_synthesis(QUESTION, [receipt(facts)])
    facts = complete_details()
    facts["sources"][1]["verifiedPhysicalPresses"] = 0
    assert not collected_lockout_ready_for_synthesis(QUESTION, [receipt(facts)])
    assert not collected_lockout_ready_for_synthesis(QUESTION, [receipt(success=False)])
    assert not collected_lockout_ready_for_synthesis(QUESTION, [])


def test_multi_objective_question_cannot_skip_additional_investigation():
    prompt = QUESTION + " Also check the scheduled jobs and hub health."
    assert not collected_lockout_ready_for_synthesis(prompt, [receipt()])
    assert not collected_lockout_ready_for_synthesis(
        "Show current motion lockout settings", [receipt()]
    )


@pytest.mark.asyncio
async def test_completed_lockout_prefetch_reaches_one_final_synthesis_no_tool_round(
    monkeypatch,
):
    class FakeMCP:
        async def list_tools(self):
            return []

    agent = UnifiedMCPAgent(
        FakeMCP(), "test-key", "gemma4:31b-cloud", ai_client=object()
    )

    async def fake_system_prompt(*args, **kwargs):
        return "Evidence-first read-only"
    monkeypatch.setattr(agent, "_system_prompt", fake_system_prompt)

    async def fake_propose(*args, **kwargs):
        return SimpleNamespace(handled=False)
    monkeypatch.setattr(agent.rule_authoring, "propose", fake_propose)

    async def fake_prefetch(host, prompt, *, catalog, messages):
        host.evidence.record(
            "homebrain_motion_lockout_investigation",
            {"appId": "4019", "lightDeviceId": "7805"},
            success=True, elapsed_ms=1,
            summary="corroborated bounded host evidence",
            effect="read", mutates=False,
            details=complete_details(),
        )
        messages.append({
            "role": "user", "content": "HOST LOCKOUT HISTORICAL EVIDENCE"
        })
        return True
    monkeypatch.setattr(orchestrator, "prefetch_motion_lockout", fake_prefetch)

    async def forbidden_tool_round(*args, **kwargs):
        raise AssertionError("No exploratory model/tool selection should run")
    monkeypatch.setattr(agent, "_chat", forbidden_tool_round)

    observed = []
    async def fake_final(messages):
        observed.append(messages)
        return (
            "Latest verified manual OFF was 12 Oct, not the later 13 Oct state. "
            "Current lockout is 300 minutes, not the requested 3 minutes. "
            "Historical lockout enforcement remains unverified."
        )
    monkeypatch.setattr(agent, "_final_answer", fake_final)

    outcome = await agent.process_user_request_result(QUESTION)
    assert "Historical lockout enforcement remains unverified" in outcome.message
    assert len(observed) == 1
    assert any("HOST LOCKOUT" in str(message.get("content"))
               for message in observed[0])
    assert outcome.request_class == "live-read"
