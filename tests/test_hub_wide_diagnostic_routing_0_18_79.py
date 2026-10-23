"""v0.18.79: source-domain complete Hubitat audits must reach bounded reasoning.

Live replay: v0.18.78's user-requested read-only comprehensive reasoning
spanned device health, app performance, scheduled jobs, and recent error logs
without saying "automation". It escaped the deterministic audit route and
timed out after 90 seconds in the general model agent.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from composite_system_audit_policy import is_cross_domain_hub_audit_request
from health_audit_service import is_comprehensive_system_audit_request


LIVE_REQUEST = """Perform a comprehensive READ-ONLY investigation of my Hubitat system.

Use current device health, application performance, scheduled jobs and recent error logs.

I want your own reasoned assessment, not a list of raw statistics.

Identify the three most important concerns, explain why each matters, compare plausible causes and alternative explanations, and rank the safest next investigations.

Pay particular attention to:
- Bedroom 3 Mesh watchdog and offline status.
- Android TV Remote certificate errors.
- Energy Usage and SenseCap D1 Settings performance.
- Scheduled-job volume and possible overlaps.

Distinguish demonstrated facts from hypotheses. Do not mistake application busy percentages for total hub CPU usage or repeated warning rows for separate outages.

Do not change any settings or devices."""


@pytest.mark.parametrize("question", [
    LIVE_REQUEST,
    "Comprehensively investigate my Hubitat system's device health, recent "
    "errors, scheduled jobs and performance. Explain the main concerns.",
    "Analyse the whole hub: health, device status, warning logs, scheduled "
    "jobs and CPU performance. Rank the evidence-backed problems.",
    "Review my hub performance and scheduler jobs, device offline health and "
    "errors in logs. Give read-only diagnostic conclusions.",
])
def test_full_hub_health_jobs_and_performance_without_rule_word(question):
    assert is_cross_domain_hub_audit_request(question)


@pytest.mark.parametrize("question", [
    "Why did Bedroom 3 Light 1 switch off at 19:30? Read its event history "
    "and relevant hub logs, not a full System Check.",
    "Show current performance and job list for one app 4019.",
    "Review the Android TV Remote certificate error log only.",
    "Check scheduled job ownership of a specific app.",
    "What's my device's offline status?",
    "Change my Hubitat light OFF now and then check the logs, "
    "scheduled jobs, device health and performance.",
])
def test_targeted_or_mutating_queries_not_broad_audit_shortcuts(question):
    # This classifier only routes cross-domain reads; write protection must
    # still be enforced by the existing top-level mutation classifier.
    if "Change my Hubitat light" in question:
        from mcp_agent_orchestrator import _explicit_mutation_request
        assert _explicit_mutation_request(question)
        return
    assert not is_cross_domain_hub_audit_request(question)


@pytest.mark.asyncio
async def test_live_request_routes_through_bounded_no_tools_audit(monkeypatch):
    import app as module

    calls = []
    async def fake_audit(audit, mcp, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            message="Deterministic read-only audit and bounded AI summary.",
            route="comprehensive-system-audit",
            request_class="live-read",
            evidence=[], choices=[], confirmation_required=False,
        )

    async def unexpected_agent(*args, **kwargs):
        raise AssertionError("Do not route whole-hub diagnostic through agent loop")

    monkeypatch.setitem(
        module.OPTIONS, "comprehensive_audit_ai_analysis_enabled", True,
    )
    monkeypatch.setattr(module, "run_comprehensive_chat_audit", fake_audit)
    monkeypatch.setattr(
        module.agent, "process_user_request_result", unexpected_agent,
    )
    result = await module._agent_request(module.ChatRequest(prompt=LIVE_REQUEST))
    assert result.route == "comprehensive-system-audit"
    assert len(calls) == 1
    assert calls[0]["analysis_focus"] == LIVE_REQUEST
    assert calls[0]["analysis_chat"] == module.agent.transport.chat


@pytest.mark.asyncio
async def test_saved_opt_out_keeps_host_only_bounded_audit(monkeypatch):
    import app as module
    calls = []

    async def fake_audit(audit, mcp, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(message="Safe read-only audit", route="comprehensive-system-audit")

    monkeypatch.setitem(
        module.OPTIONS, "comprehensive_audit_ai_analysis_enabled", False,
    )
    monkeypatch.setattr(module, "run_comprehensive_chat_audit", fake_audit)
    result = await module._agent_request(module.ChatRequest(prompt=LIVE_REQUEST))
    assert result.route == "comprehensive-system-audit"
    assert calls == [{}]


@pytest.mark.asyncio
async def test_explicit_write_is_not_swallowed_by_system_check(monkeypatch):
    import app as module

    async def unexpected_audit(*args, **kwargs):
        raise AssertionError("Write request must not be diverted to read-only audit")

    async def controlled_agent(*args, **kwargs):
        return SimpleNamespace(
            message="Write request is governed by the agent confirmation gate.",
            route="unified-mcp-agent", request_class="write", evidence=[],
        )

    monkeypatch.setattr(module, "run_comprehensive_chat_audit", unexpected_audit)
    monkeypatch.setattr(
        module.agent, "process_user_request_result", controlled_agent,
    )
    request = (
        "Switch Bedroom 3 Light 1 OFF now, then check my Hubitat health, "
        "device errors, scheduled jobs, warning logs and performance."
    )
    result = await module._agent_request(module.ChatRequest(prompt=request))
    assert result.route == "unified-mcp-agent"


@pytest.mark.parametrize("prompt,expected", [
    ("Change my Hubitat light OFF now, and then check the logs.", True),
    ("Please change my lamp on", True),
    ("Explain the change in light OFF event history.", False),
    ("Check whether the light changed to OFF.", False),
])
def test_bounded_change_imperatives_are_not_descriptive_reads(prompt, expected):
    from mcp_agent_orchestrator import _explicit_mutation_request
    assert _explicit_mutation_request(prompt) is expected


def test_other_existing_full_audit_syntax_is_unchanged():
    q = ("Run a comprehensive hub audit: inspect all automation rules, "
         "installed apps, sensors, errors and device states.")
    assert is_cross_domain_hub_audit_request(q) or is_comprehensive_system_audit_request(q)
