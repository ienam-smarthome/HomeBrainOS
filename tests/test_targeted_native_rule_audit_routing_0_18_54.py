"""v0.18.54 regression: named TV rules must not trigger whole-hub audit.

The live v0.18.53 attempt returned route=comprehensive-system-audit,
205 devices, 156 automations and no app 4239/4241 evidence. The source
trace does NOT include the original user's submitted request. Replay
the immediately preceding recommended verification text plus variants.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from targeted_rule_scope_policy import (  # noqa: E402
    is_targeted_rule_investigation, named_rule_app_ids,
)
from composite_system_audit_policy import is_cross_domain_hub_audit_request  # noqa: E402
from health_audit_service import is_comprehensive_system_audit_request  # noqa: E402
from automation_diagnostic_policy import is_broad_automation_runtime_diagnostic  # noqa: E402
from rule_machine_analysis import requires_rule_logic_inspection  # noqa: E402

ACTUAL_RECOMMENDED_PROMPT = (
    "Perform a read-only verification of Rule Machine apps 4239 and 4241. "
    "First read native rule health and local variables for app 4239. "
    "Then inspect whether TV_Minutes_Used is a global Hub Variable or a local "
    "Rule Machine variable, and establish exactly which variable app 4241 "
    "resets. Compare the variable references, not just their names. "
    "Verify the one-minute delayed loop, cancelable delay behaviour, "
    "60-minute threshold and reset action. Check available event/command "
    "history for Internet device 6923. Distinguish configuration from "
    "confirmed execution. Do not modify any rules, variables or devices."
)


@pytest.mark.parametrize("question,ids", [
    (ACTUAL_RECOMMENDED_PROMPT, ("4239", "4241")),
    ("Inspect Rule Machine apps 4239 and 4241, variables and triggers.", ("4239", "4241")),
    ("Review rules 4239, 4241, and 3985 for overlapping conditions.", ("4239", "4241", "3985")),
    ("Verify Rule Machine app ID 4239 counter, threshold and reset.", ("4239",)),
    ("Read app 4239 and Internet device 6923 action history.", ("4239",)),
])
def test_bounded_named_rule_ids_and_device_exclusion(question, ids):
    assert named_rule_app_ids(question) == ids
    assert is_targeted_rule_investigation(question)
    assert requires_rule_logic_inspection(question)


@pytest.mark.parametrize("question", [
    ACTUAL_RECOMMENDED_PROMPT,
    "Review rule 4239 health, logs, conditions and Internet device 6923.",
    "Investigate apps 4239 and 4241: hub variables, device history, "
    "log errors, native automation schedule, rule health and reset logic.",
    "Review app 4239 trigger events, disabled status, devices 4221/6923, "
    "and Hub Variable history for potential failures.",
])
def test_audit_classifiers_must_all_defer_targeted_named_rule(question):
    assert is_targeted_rule_investigation(question)
    assert not is_cross_domain_hub_audit_request(question)
    assert not is_comprehensive_system_audit_request(question)
    assert not is_broad_automation_runtime_diagnostic(question)


@pytest.mark.parametrize("question", [
    "Perform a comprehensive read-only audit of my entire Hubitat hub, "
    "including apps 4239 and 4241, all devices, logs and automation rules.",
    "Review the full hub: automations, device targets and scheduled jobs "
    "and show rule 4239 among the sampled results.",
    "Audit all my automations and devices, including rule 4239, "
    "for health, scheduler errors and overlap.",
])
def test_explicit_global_audits_still_allowed_with_named_example(question):
    assert not is_targeted_rule_investigation(question)
    assert (
        is_cross_domain_hub_audit_request(question)
        or is_comprehensive_system_audit_request(question)
        or is_broad_automation_runtime_diagnostic(question)
    )


def test_hub_variable_is_not_entire_hub_audit():
    assert is_targeted_rule_investigation(
        "Inspect app 4239 counter and its Hub Variable reference, "
        "then compare rule 4241 reset action."
    )
    assert named_rule_app_ids(
        "Inspect app 4239 counter and its Hub Variable reference, "
        "then compare rule 4241 reset action."
    ) == ("4239", "4241")


@pytest.mark.asyncio
async def test_actual_request_reaches_scoped_model_not_health_audit(monkeypatch):
    import app as application

    calls = []

    async def forbidden_audit(*args, **kwargs):
        raise AssertionError("Never run 205-device System Check for named rules")

    async def fake_native_rule_investigation(prompt, history, *, session_id="default"):
        calls.append((prompt, session_id))
        return SimpleNamespace(
            route="unified-mcp-agent",
            request_class="live-read",
            message="Native rule 4239 and 4241 evidence under investigation",
            evidence=[{"tool": "hub_read_rules", "sub_tool": "hub_get_rule_health",
                       "success": True, "effect": "read", "mutates": False}],
            investigation_coverage=None,
        )

    async def passthrough(agent, mcp, outcome, prompt):
        return outcome

    monkeypatch.setattr(application, "run_comprehensive_chat_audit", forbidden_audit)
    monkeypatch.setattr(
        application.agent, "process_user_request_result",
        fake_native_rule_investigation,
    )
    monkeypatch.setattr(application, "finalize_performance_api_outcome", passthrough)
    outcome = await application._agent_request(
        application.ChatRequest(prompt=ACTUAL_RECOMMENDED_PROMPT,
                                model_tier="free", session_id="4239-test")
    )
    assert calls == [(ACTUAL_RECOMMENDED_PROMPT, "4239-test")]
    assert outcome.route == "unified-mcp-agent"
    assert outcome.evidence[0]["tool"] == "hub_read_rules"
