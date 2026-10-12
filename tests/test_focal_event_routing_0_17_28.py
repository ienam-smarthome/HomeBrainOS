"""Regressions for the 0.17.27 live misroute to comprehensive System Check.

The 12-Oct-2026 Bedroom 1 Light question asked for a historical causal
investigation, but the broad automation gate matched the word 'which' in
'which history source' and launched a 214-device System Check.
These are pure intent tests: no hub connection, AI or device mutations.
"""
from __future__ import annotations

import pytest

from automation_diagnostic_policy import (
    has_broad_automation_scope,
    is_automation_runtime_diagnostic,
    is_broad_automation_runtime_diagnostic,
    is_targeted_device_transition_investigation,
)
from automation_status_service import AutomationStatusService
from health_audit_service import is_comprehensive_system_audit_request
from performance_host_plan import is_broad_performance_request


LIVE_QUESTION = (
    "Investigate why Bedroom 1 Light switched OFF at approximately 17:14:05 "
    "on 12 October 2026. Check the Historical Journal first, then use "
    "bounded MCP history only where necessary. Correlate available motion, "
    "button and automation evidence with this exact OFF event. Explain what "
    "is verified, what remains uncertain, and which history source supports "
    "each conclusion. Read-only."
)


@pytest.mark.parametrize("question", [
    LIVE_QUESTION,
    "Investigate why Bedroom 1 Light switched OFF at 17:14:05; "
    "check device history, app logs and which automation was responsible.",
    "Why did Bedroom 1 Light turn off at 17:14? "
    "Which automations could have caused it?",
    "Investigate why Kitchen Light switched OFF yesterday; "
    "check all relevant automation logs and which source proves the cause.",
    "Explain why Hallway Light switched ON at 08:16; "
    "inspect my automations only as possible triggers.",
])
def test_exact_device_transition_never_runs_a_whole_hub_audit(question):
    assert is_targeted_device_transition_investigation(question)
    assert not is_broad_automation_runtime_diagnostic(question)
    assert not is_comprehensive_system_audit_request(question)
    assert not is_broad_performance_request(question)
    assert not AutomationStatusService.matches_request(question)


@pytest.mark.parametrize("question", [
    "Investigate which history source supports the Bedroom 1 automation evidence?",
    "Investigate why a rule failed; which log entries explain it?",
    "Diagnose app 4015 not triggering; which device caused it?",
    "Review automation execution on the Bedroom 1 dimmer and which events matched.",
])
def test_unrelated_which_and_device_words_do_not_grant_broad_scope(question):
    assert is_automation_runtime_diagnostic(question)
    assert not has_broad_automation_scope(question)
    assert not is_broad_automation_runtime_diagnostic(question)


@pytest.mark.parametrize("question", [
    "Investigate why all my automations are failing",
    "Which of my automations have failed to execute?",
    "Audit all rules and their app logs",
    "Check every automation for runtime failures",
    "Diagnose automation errors across my hub",
    "Review my automations for broken actions",
    "Inspect all automation logs for failures",
])
def test_genuinely_global_automation_diagnostics_still_use_audit(question):
    assert is_broad_automation_runtime_diagnostic(question)


@pytest.mark.parametrize("question", [
    "Investigate why app 4015 failed at 17:14",
    "Why did rule 4015 not execute yesterday?",
    "Inspect the Bedroom 1 Lights Off automation for an invalid target",
])
def test_targeted_app_diagnostics_stay_narrow(question):
    assert is_automation_runtime_diagnostic(question)
    assert not is_broad_automation_runtime_diagnostic(question)


@pytest.mark.parametrize("question", [
    "Run system check",
    "Run a full system audit",
    "Comprehensive system audit including recent app and device logs",
])
def test_explicit_system_audit_is_still_honoured(question):
    assert is_comprehensive_system_audit_request(question)
