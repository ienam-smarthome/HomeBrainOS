"""Live 23 Oct 2026 regression: existing Rule Machine audit is read-only.

The v0.18.71 response ran 11 read-only calls, yet was classed as a write
because the prompt included a hypothetical "could switch ... OFF". A separate
app inventory/list was wrongly promoted to a device identity, provoking an
unrelated device-state lookup and a final refusal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from device_claim_grounding import (
    extract_tool_message_device_identities, find_named_device_mismatch,
)
from investigation_intelligence import plan_investigation
from mcp_agent_orchestrator import _explicit_mutation_request, UnifiedMCPAgent


LIVE_READ_ONLY_RULE_AUDIT = """Perform a comprehensive READ-ONLY verification of existing
Rule Machine app 4246, "Livingroom Light 1 – Night Idle OFF – TEST", and
compare it with existing Light Mode Controller app 4019.

1. Retrieve app 4246's persisted triggers, complete ordered action sequence,
nested IF conditions, cancelDelay action, 10-minute cancelable delay,
closing endIf actions and nighttime window (23:00–06:00).
2. Inspect app 4246's actual health, stopped/broken status and local variables.
3. Check the complete Rule Machine inventory for exact-name duplicates.
4. Retrieve app 4019's persisted inactivity-OFF duration, backup-OFF delay
and manual-OFF motion-lockout configuration.
5. Determine whether app 4019 could switch Livingroom Light 1 (device 7805)
OFF before app 4246's 10-minute delay completes.
6. For every finding, distinguish verified typed evidence, unverified
configuration text and runtime behaviour requiring event/log evidence.

Show actual source fields. Do not mark unsupported findings VERIFIED.
Report investigation_coverage and evidenceComplete.
This is an investigation of installed rules, NOT a new-rule design request.
Do not propose, create, modify, execute or disable anything.
Do not request confirmation."""


def test_live_rule_audit_is_not_write_intent():
    assert _explicit_mutation_request(LIVE_READ_ONLY_RULE_AUDIT) is False
    plan = plan_investigation(LIVE_READ_ONLY_RULE_AUDIT)
    assert plan is not None and plan.domain == "existing_rule_verification"


@pytest.mark.parametrize("request", [
    LIVE_READ_ONLY_RULE_AUDIT
    + "\nDo not create, modify, execute or disable anything.",
    "Review the persisted actions of Rule Machine app 4246. Determine whether "
    "app 4019 could switch Livingroom Light 1 OFF first. Do not create or modify.",
    "Perform a READ-ONLY verification of Rule Machine app 4246's ordered "
    "actions and conditions. Could app 4019 switch Livingroom Light 1 OFF?",
])
def test_hypothetical_switch_off_still_read_only(request):
    assert _explicit_mutation_request(request) is False


@pytest.mark.parametrize("request", [
    "Review the persisted actions of Rule Machine app 4246. Then switch "
    "Livingroom Light 1 OFF.",
    "Perform a READ-ONLY verification of Rule Machine app 4246's ordered "
    "actions. Also disable app 4019.",
    "Review Rule Machine app 4246 persisted actions.\n"
    "Disable app 4019 now.",
    "Disable Rule Machine app 4246. Inspect persisted actions first.",
])
def test_independent_explicit_writes_remain_writes(request):
    assert _explicit_mutation_request(request) is True


def test_app_inventory_and_configuration_do_not_create_fake_devices():
    tool_messages = [
        {"role": "tool", "content": json.dumps({
            "result": {
                "apps": [
                    {"id": 4019, "label": "Livingroom Light 1 (⚪ Lights Off, 🏃 Motion Active)"},
                    {"id": 4246, "label": "Livingroom Light 1 – Night Idle OFF – TEST"},
                ], "count": 2,
            }
        })},
        {"role": "tool", "content": json.dumps({
            "result": {
                "app": {"id": "4019", "label": "Livingroom Light 1 (⚪ Lights Off, 🏃 Motion Active)"},
                "childApps": [{"id": "4246", "label": "Livingroom Light 1 – Night Idle OFF – TEST"}],
                "rules": [{"id": 4246, "label": "Livingroom Light 1 – Night Idle OFF – TEST"}],
            }
        })},
        {"role": "tool", "content": json.dumps({
            "result": {"devices": [{"id": "7805", "label": "Livingroom Light 1"}]}
        })},
        {"role": "tool", "content": json.dumps({
            "result": {"deviceId": "7805", "label": "Livingroom Light 1"}
        })},
    ]
    identities = extract_tool_message_device_identities(tool_messages)
    assert identities == [{"id": "7805", "label": "Livingroom Light 1"}]
    assert find_named_device_mismatch(
        "App Livingroom Light 1 (⚪ Lights Off, 🏃 Motion Active) "
        "turned off Livingroom Light 1.",
        identities, {"7805"},
    ) is None


def test_real_other_device_still_triggers_grounding():
    tool_messages = [{"role": "tool", "content": json.dumps({
        "apps": [{"id": "4019", "label": "Livingroom Light 1 (⚪ Lights Off, 🏃 Motion Active)"}],
        "devices": [
            {"id": "7805", "label": "Livingroom Light 1"},
            {"id": "7806", "label": "Other Light"},
        ],
    })}]
    identities = extract_tool_message_device_identities(tool_messages)
    assert find_named_device_mismatch(
        "Other Light is currently on.", identities, {"7805"},
    ) == "Other Light"


@pytest.mark.asyncio
async def test_read_only_audit_yields_live_read_class_and_evidence_coverage(monkeypatch):
    class NoHubWrites:
        pass

    async def mocked_agent(self, user_prompt, conversation_history=None, *,
                           session_id="default"):
        self.evidence.record(
            "hub_read_rules",
            {"tool": "hub_get_rule_health", "args": {"appId": "4246"}},
            success=True, elapsed_ms=1, summary="typed app 4246 health",
            supports_live_claim=True, evidence_kind="native_rule_evidence",
            details={
                "appId": "4246",
                "verifiedHealth": {"stopped": False, "broken": False},
            },
        )
        return "App 4246 has six verified triggers."  # not typed; guard must qualify

    monkeypatch.setattr(UnifiedMCPAgent, "_process_user_request", mocked_agent)
    agent = UnifiedMCPAgent(NoHubWrites(), "unused")
    outcome = await agent.process_user_request_result(LIVE_READ_ONLY_RULE_AUDIT)
    assert outcome.request_class == "live-read"
    assert outcome.investigation_coverage["domain"] == "existing_rule_verification"
    assert outcome.investigation_coverage["evidenceComplete"] is False
    assert "Not independently verified" in outcome.message
    assert "six verified triggers" not in outcome.message
    assert outcome.confirmation_required is False
    assert all(not row.get("mutates") for row in outcome.evidence)
