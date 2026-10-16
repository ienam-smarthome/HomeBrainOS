"""0.17.91 regression coverage for broad audits and telemetry epistemic scope."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "hubitat-mcp-ai" / "rootfs" / "app"))

from shared_investigation_completion import apply_shared_investigation_completion
from system_audit_coverage import assess_system_audit_sources
from evidence_claim_calibrator import calibrate_supported_conclusions


def _outcome(route, evidence, message="System Check findings"):
    return SimpleNamespace(
        route=route,
        request_class="live-read",
        message=message,
        evidence=evidence,
        metrics={"outcome":"success","counters":{"tool_calls":3}},
    )


def _health_receipts():
    return [
        {"tool":"health_audit.run", "success":True,
         "evidence_kind":"read_only_system_audit_snapshot"},
        *[
            {"tool":"health_audit.run", "sub_tool":part,
             "success":True, "evidence_kind":"audit_source_section",
             "summary":f"{part} section available; "+count+" records/items in the returned source"}
            for part,count in (("devices","207"),("automations","152"),("logs","200"))
        ],
        {"tool":"hub_manage_logs","sub_tool":"hub_get_performance_stats",
         "success":True,"evidence_kind":"chat_audit_performance_stats"},
    ]


def test_comprehensive_system_audit_not_historical_causality():
    question = (
        "Perform a comprehensive read-only audit of my Hubitat hub. "
        "Correlate offline devices, logs and performance concerns, "
        "rank likely causes and evidence-based recommendations."
    )
    answer = apply_shared_investigation_completion(
        _outcome("comprehensive-system-audit", _health_receipts()), question
    )
    scope = answer.investigation_coverage
    assert scope["domain"] == "system_health_audit"
    assert scope["sourceCoverage"]["missingSourceKinds"] == []
    assert set(scope["sourceCoverage"]["checkedSourceKinds"]) == {
        "audit_devices", "audit_automations", "audit_logs"
    }
    assert "device_history" not in scope["sourceCoverage"]["requiredSourceKinds"]
    assert "command_history" not in scope["sourceCoverage"]["requiredSourceKinds"]
    assert scope["status"] == "partial-evidence"
    assert "bounded sample" in scope["sourceIntegrityWarnings"][0]
    assert "upstream initiator" not in answer.message
    assert answer.metrics["outcome"] == "unresolved"


def test_missing_audit_section_visible_as_unchecked_not_healthy():
    data = _health_receipts()
    data[2]["success"] = False  # automations section
    answer = apply_shared_investigation_completion(
        _outcome("comprehensive-system-audit", data),
        "Run a comprehensive hub audit of devices and automations",
    )
    assert answer.investigation_coverage["sourceCoverage"]["missingSourceKinds"] == [
        "audit_automations"
    ]
    assert "audit_automations" in answer.message
    assert "Do not infer" in answer.message


def _performance_receipts():
    return [
        {"tool":"hub_read_diagnostics","sub_tool":"hub_get_metrics",
         "success":True,"evidence_kind":"host_planned_performance_source"},
        {"tool":"hub_manage_logs","sub_tool":"hub_get_performance_stats",
         "success":True,"evidence_kind":"host_planned_performance_source"},
        {"tool":"hub_manage_logs","sub_tool":"hub_get_logs",
         "success":True,"evidence_kind":"host_planned_performance_source"},
    ]


def test_model_led_system_audit_does_not_conflate_device_status_with_performance():
    prompt = ("Review Hubitat system performance and unavailable device "
              "health; investigate load and recommend safe next checks")
    answer = apply_shared_investigation_completion(
        _outcome("unified-mcp-agent", _performance_receipts()), prompt
    )
    scope = answer.investigation_coverage
    assert scope["domain"] == "system_performance_audit"
    assert scope["sourceCoverage"]["missingSourceKinds"] == ["device_state"]
    assert "device_history" not in scope["sourceCoverage"]["requiredSourceKinds"]
    assert "device_state" in answer.message


def test_performance_only_audit_not_requires_unrequested_device_state():
    result = assess_system_audit_sources(
        "unified-mcp-agent", "Review Hubitat performance and latency",
        _performance_receipts(),
    )
    assert result["status"] == "source-checks-complete"
    assert result["sourceCoverage"]["missingSourceKinds"] == []


def test_targeted_light_causal_question_not_misrouted_as_hub_audit():
    result = assess_system_audit_sources(
        "unified-mcp-agent",
        "Why did living room light turn ON? Review its app history.",
        _performance_receipts(),
    )
    assert result is None


def _watchdog_receipts():
    return [
        {"success":True, "tool":"homebrain_device_history",
         "evidence_kind":"deterministic_device_event_history",
         "details":{"historySourceIntegrityVerified":False,
                    "observedEventsTruncated":True}},
        {"success":True,"tool":"hub_read_diagnostics",
         "sub_tool":"hub_get_logs",
         "arguments":{"tool":"hub_get_logs",
                      "args":{"deviceId":"7103","since":"24h"}},
         "details":{"logCount":62, "logs":[{
             "message":"dev|7103|Bedroom 3 Mesh|Watchdog fired after 39018s without data — reconnecting",
             "date":"2026-10-16 18:06:23.773",
         }]}},
    ]


def test_actual_bedroom_mesh_answer_calibrates_source_claims_and_bold_confidence():
    message = (
        "### Investigation: Bedroom 3 Mesh\n"
        "**Strongest Supported Cause:** **Telemetry Silence / Application-Layer Failure.**\n"
        "**Confidence:** High\n"
        "The device is experiencing a complete cessation of telemetry updates.\n"
        "| Oct 12 | **Last Successful Telemetry** | The last time the device successfully reported state. |\n"
        "| Oct 16 | **Transport Layer Restored** | mqttStatus connected |\n"
        "This proves the MQTT session is active, but the Tasmota "
        "device is not publishing its telemetry (tele topics) to the broker.\n"
        "The watchdog is firing in a tight loop.\n"
    )
    output, labels = calibrate_supported_conclusions(
        message, _watchdog_receipts(), domain="device_telemetry",
    )
    assert "High" not in output
    assert "strongest supported observation" in output.lower()
    assert "complete cessation of telemetry updates" not in output
    assert "Last Successful Telemetry" not in output
    assert "This proves the MQTT session is active" not in output
    assert "transport layer restored" not in output.lower()
    assert "not independently verified" in output.lower()
    assert "tight loop" not in output
    assert "unqualified_high_confidence" in labels
    assert "watchdog_communication_scope" in labels


def test_identical_nested_hypothesis_removed_without_dropping_other_bullets():
    repeated = ("The scoped diagnostic read returned 24 log rows in 6h, "
                "including explicit diagnostic signal(s): timeout. These "
                "observations support a calibrated failure/connectivity "
                "hypothesis, but do not prove the exact mechanism.")
    message = (
        f"*   **OpenWeatherMap Connectivity:** {repeated}\n"
        f"    *   {repeated}\n"
        "    *   **Next check:** Inspect the source-side error status.\n"
        "*   **MCP Rule Server:** Different measured concern.\n"
    )
    output, labels = calibrate_supported_conclusions(message, [])
    assert output.count(repeated) == 1
    assert "Next check" in output
    assert "MCP Rule Server" in output
    assert "duplicate_summary_removed" in labels


def test_no_regression_for_truthful_fully_scoped_diagnosis_or_log_records():
    message = (
        "**Confidence:** High\n"
        "| Event | Recorded value |\n| --- | --- |\n"
        "| deviceHealth | stale |\n"
    )
    assert calibrate_supported_conclusions(message, [], domain="device_telemetry") == (
        message, ()
    )
