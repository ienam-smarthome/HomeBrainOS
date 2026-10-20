"""v0.18.44 regression: full-hub dependency audits reach the bounded host route."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from composite_system_audit_policy import is_cross_domain_hub_audit_request
from automation_dependency_probe import summarise_config, analyse_dependency_probes


LIVE_DEPENDENCY_PROMPT = (
    "Perform a comprehensive read-only audit of my entire Hubitat hub. "
    "Investigate scheduled jobs, disabled automations, heartbeat monitoring "
    "and potentially overlapping lighting rules. Read actual available app "
    "configurations, compare triggers, actions and target devices, "
    "distinguish verified dependencies from possible overlaps, and "
    "prioritise the most important findings. Do not make changes."
)


@pytest.mark.parametrize("question,expected", [
    (LIVE_DEPENDENCY_PROMPT, True),
    ("Audit my entire Hubitat hub for scheduled jobs, installed app rules, "
     "shared targets and configuration dependencies.", True),
    ("Review the full hub: automations, device targets and scheduled jobs "
     "to identify overlapping rule triggers.", True),
    ("Audit the entire hub automations, scheduled jobs and shared action targets.", True),
    ("Audit my entire Hubitat hub for scheduled jobs, automations, performance "
     "targets and dependencies.", False),
    ("Analyse all scheduled jobs and group by handler.", False),
    ("Review my hub performance and reduce overhead, read-only.", False),
    ("Check the schedule for my one Bedroom 1 Light rule.", False),
    ("Why did Bedroom 1 light turn OFF at 01:30?", False),
    ("Disable automations for the kitchen.", False),
])
def test_full_hub_dependency_audit_dispatch_boundary(question, expected):
    assert is_cross_domain_hub_audit_request(question) is expected


def test_live_prompt_routes_to_host_audit_without_general_model(monkeypatch):
    import app as application

    received = []

    async def run_host(audit, gateway):
        received.append((audit, gateway))
        return SimpleNamespace(
            route="comprehensive-system-audit",
            request_class="live-read",
            message="Automation configuration and dependency investigation",
            evidence=[{"evidence_kind": "chat_audit_app_dependency_configuration",
                       "success": True, "effect": "read", "mutates": False}],
        )

    async def disallowed_general_agent(*args, **kwargs):
        raise AssertionError("Comprehensive dependency audit must not use general agent")

    monkeypatch.setattr(application, "run_comprehensive_chat_audit", run_host)
    monkeypatch.setattr(application.agent, "process_user_request_result",
                        disallowed_general_agent)
    monkeypatch.setitem(application.OPTIONS, "comprehensive_audit_ai_analysis_enabled", False)
    monkeypatch.setitem(application.OPTIONS, "automation_diagnostic_ai_analysis_enabled", False)

    response = asyncio.run(application._agent_request(
        application.ChatRequest(prompt=LIVE_DEPENDENCY_PROMPT, model_tier="free")
    ))
    assert response.route == "comprehensive-system-audit"
    assert "Automation configuration" in response.message
    assert received == [(application.health_audit, application.mcp)]


def _structured_page(app_id, action_id=None, trigger_id=None):
    """Action-only typed device data without optional action prose."""
    return {
        "success": True,
        "app": {"id": int(app_id)},
        "page": {
            "sections": [{
                "title": "Current configuration",
                "paragraphs": [],
                "inputs": [{"deviceId": trigger_id}] if trigger_id else [],
            }],
            "actions": [{"targetDeviceIds": [action_id]}] if action_id else [],
        },
    }


def test_structured_target_overlap_does_not_require_action_paragraphs():
    a = summarise_config(_structured_page("3992", action_id=7339), "3992")
    b = summarise_config(_structured_page("3931", action_id=7339), "3931")
    assert a["actionTextPresent"] is False
    assert b["actionTextPresent"] is False
    comparison = analyse_dependency_probes([
        {"id": "3992", **a}, {"id": "3931", **b},
    ])
    assert comparison["typedActionDeviceOverlaps"][0]["targetDeviceIds"] == ["7339"]
    assert comparison["textOnlyActionCandidates"] == []
    assert comparison["historicalExecutionVerified"] is False
    assert comparison["callbackOwnersVerified"] is False


def test_trigger_device_identity_is_not_mistaken_for_action_target():
    a = summarise_config(_structured_page("3992", trigger_id=7339), "3992")
    b = summarise_config(_structured_page("3931", trigger_id=7339), "3931")
    assert a["typedActionDeviceIds"] == []
    assert b["typedActionDeviceIds"] == []
    assert analyse_dependency_probes([
        {"id": "3992", **a}, {"id": "3931", **b},
    ])["typedActionDeviceOverlaps"] == []


def test_wrong_app_id_does_not_verify_structured_target():
    assert summarise_config(_structured_page("3992", action_id=7339), "3931") is None
