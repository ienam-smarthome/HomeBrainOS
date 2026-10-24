"""2026-10-24 Claude comparison: a deep single-device question must use the AI/MCP loop.

The HomeBrain 0.18.91 result wrongly ran a 204-device System Check, 160 app
inventory and 278-job scheduler report instead of reading device 7103 history
and installed Tasmota driver source. These tests cover the objective/scope
boundary without any live device or Hubitat mutation.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from investigation_objective import (
    resolve_primary_objective, scoped_device_investigation_id,
)
from health_audit_service import is_comprehensive_system_audit_request
from composite_system_audit_policy import is_cross_domain_hub_audit_request
from automation_diagnostic_policy import is_broad_automation_runtime_diagnostic
from performance_host_plan import is_broad_performance_request

QUESTION = """Perform a comprehensive READ-ONLY root-cause investigation of
Bedroom 3 Mesh (Hubitat device ID 7103).

Investigate independently using available live Hubitat MCP tools.
1. Determine current state and last successful communication.
2. Examine device-specific logs, watchdog warnings and historical events.
3. Inspect relevant device driver, application configuration, scheduled jobs
and automations where they could explain the behaviour.
4. Explain why MQTT connected does not prove the physical device is online.
5. Investigate physical connectivity, stale telemetry, MQTT status, power or
another cause.
6. Correlate evidence chronologically, distinguishing cached attributes.
7. Identify the most likely root cause and competing hypotheses.

Choose relevant MCP tools independently; verify identity before claims.
Do not modify any Hubitat devices, drivers, apps or settings."""


def test_claude_comparison_question_is_targeted_despite_diagnostic_vocabulary():
    objective = resolve_primary_objective(QUESTION)
    assert objective.domain == "targeted_device"
    assert objective.target_device_id == "7103"
    assert not is_comprehensive_system_audit_request(QUESTION)
    assert not is_cross_domain_hub_audit_request(QUESTION)
    # The main API checks the objective before every generic fast shortcut.
    app_py = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "targeted_device = primary_objective.is_targeted_device" in app_py
    assert 'and not targeted_device and not targeted_rule' in app_py
    assert "if not targeted_device and is_broad_performance_request" in app_py


def test_other_single_device_queries_remain_scoped():
    for question in [
        "Why is Hubitat device ID 7103 offline? Read current device and logs.",
        "Diagnose device 7103, compare apps and jobs and inspect driver.",
        "Read-only: investigate Bedroom 3 Mesh (device ID 7103) end to end.",
    ]:
        assert scoped_device_investigation_id(question) == "7103"
        assert resolve_primary_objective(question).is_targeted_device
        assert not is_comprehensive_system_audit_request(question)


def test_real_whole_hub_audit_with_example_device_remains_broad():
    for question in [
        "Perform a comprehensive system audit with logs, devices, apps and jobs; include device 7103.",
        "Audit the entire hub, inspect automations and device ID 7103 as one example.",
        "Review all devices including device 7103 and app schedules with logs.",
    ]:
        assert scoped_device_investigation_id(question) is None
        assert not resolve_primary_objective(question).is_targeted_device


def test_multiple_device_ids_do_not_select_one_arbitrarily():
    request = "Compare device 7103 and device 7104 histories and related app rules."
    assert scoped_device_investigation_id(request) is None


def test_generic_system_check_keeps_shortcut():
    assert is_comprehensive_system_audit_request(
        "Perform a comprehensive system audit of my Hubitat devices, apps, and logs"
    )
    assert is_cross_domain_hub_audit_request(
        "Perform comprehensive Hubitat system audit of devices, logs, "
        "applications, scheduler jobs and performance"
    )
