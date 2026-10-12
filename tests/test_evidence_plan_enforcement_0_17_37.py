"""0.17.37: enforce source scope across MCP execution and finalisation."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from evidence_gateway_contract import normalize_gateway_read, missing_required_read_fields
from investigation_intelligence import plan_investigation, assess_investigation
from performance_host_plan import is_scheduler_only_evidence_request


def _receipt(tool, details=None, args=None, *, kind="tool_result"):
    return {
        "tool": "hub_read_devices", "sub_tool": tool,
        "arguments": {"tool": tool, "args": args or {}},
        "details": details or {}, "success": True,
        "evidence_kind": kind,
    }


def test_nested_gateway_log_scope_normalized_before_hub_call():
    request = {
        "tool": "hub_get_logs",
        "args": {"tool": "hub_get_logs", "args": {
            "deviceId": "7103", "since": "24h", "limit": 100,
        }},
    }
    normalized = normalize_gateway_read("hub_read_diagnostics", request)
    assert normalized == {"tool": "hub_get_logs", "args": {
        "deviceId": "7103", "since": "24h", "limit": 100,
    }}
    assert request["args"]["tool"] == "hub_get_logs"
    assert not missing_required_read_fields("hub_read_diagnostics", normalized)


def test_missing_device_attribute_rejected_without_guessing_one():
    request = {"tool": "hub_get_device_attribute",
               "args": {"deviceId": "7103"}}
    assert missing_required_read_fields("hub_manage_devices", request) == ("attribute",)
    assert normalize_gateway_read("hub_manage_devices", request) == request


def test_commands_are_not_rewritten_by_read_gateway_normalizer():
    command = {"tool": "hub_call_device_command",
               "args": {"tool": "hub_call_device_command", "args": {
                   "deviceId": "7103", "command": "off",
               }}}
    assert normalize_gateway_read("hub_manage_devices", command) == command
    assert missing_required_read_fields("hub_manage_devices", command) == ()


def test_lockout_structured_collector_is_evaluated_without_configuration_proof():
    plan = plan_investigation(
        "Investigate the latest manual OFF of Livingroom Light 1 "
        "followed by motion; did the three-minute motion lockout engage?"
    )
    assert plan is not None and plan.domain == "manual_motion_lockout"
    collected = {
        "status": "partial-focal-sequence", "focalOff": "2026-10-12T19:00:00Z",
        "sources": [
            {"source": "bounded-light-device-history", "success": True},
            {"source": "bounded-app-execution-logs", "readSucceeded": True,
             "returnedRows": 0},
        ],
        "journal": [
            {"kind": "button", "observations": []},
            {"kind": "sensor", "observations": [{
                "observedAt": "2026-10-12T19:00:15Z", "value": "active",
                "timestampBasis": "collector-received",
            }]},
        ],
        "nearbyButtonEvents": [], "lockoutExecutionVerified": False,
    }
    receipts = [{
        "tool": "homebrain_motion_lockout_investigation",
        "sub_tool": None, "success": True, "details": collected,
    }, _receipt("hub_get_app_config", {"app": {"id": "4019"}},
                 {"appId": "4019"})]
    outcome = assess_investigation(plan, receipts)
    mapping = {r["key"]: r["state"] for r in outcome["requirements"]}
    assert mapping == {
        "target_off": "observed", "controller": "checked-unverified",
        "motion": "checked-unverified", "execution": "checked-unverified",
    }
    # Observed motion without verified activation-source eligibility does not
    # prove an attempted motion-controlled ON or lockout decision.
    assert any("eligibility" in msg for msg in outcome["warnings"])
    assert outcome["evidenceComplete"] is False


def test_unrelated_log_rows_are_not_treated_as_device_watchdog_evidence():
    plan = plan_investigation(
        "Diagnose whether Bedroom 3 Mesh MQTT telemetry is stale or offline."
    )
    assert plan is not None
    evidence = [
        _receipt("hub_get_device", {}, {"deviceId": "7103"}),
        _receipt("hub_get_logs", {"logs": [
            {"message": "dev|7778|Kitchen|motion active"},
            {"message": "app|2817|TV power wait event"},
        ]}, {"args": {"deviceId": "7103"}, "tool": "hub_get_logs"}),
    ]
    outcome = assess_investigation(plan, evidence)
    status = {x["key"]: x["state"] for x in outcome["requirements"]}
    assert status["watchdog"] == "checked-unverified"
    evidence[1]["details"]["logs"].append({
        "message": "dev|7103|Bedroom 3 Mesh|watchdog reconnecting"
    })
    outcome2 = assess_investigation(plan, evidence)
    status2 = {x["key"]: x["state"] for x in outcome2["requirements"]}
    assert status2["watchdog"] == "observed"


def test_only_scheduler_evidence_path_skips_general_logs():
    prompt = ("Analyse all scheduled jobs on my Hubitat hub, grouped by "
              "handler and verified owning app where available, for efficiency.")
    assert is_scheduler_only_evidence_request(prompt)
    assert not is_scheduler_only_evidence_request(
        "Analyse whole hub performance and scheduled jobs for efficiency."
    )


def test_executor_rejects_incomplete_attribute_read_before_network():
    from tool_executor import ToolExecutor

    class MCP:
        calls = 0
        async def call_tool(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("Network call must not be made")

    class Evidence:
        def __init__(self):
            self.rows = []
        def record(self, *a, **kw):
            self.rows.append((a, kw))

    hub, evidence = MCP(), Evidence()
    executor = ToolExecutor(hub, evidence)
    result = asyncio.run(executor.execute(
        "hub_manage_devices",
        {"tool": "hub_get_device_attribute", "args": {"deviceId": "7103"}},
    ))
    assert result.success is False
    assert hub.calls == 0
    assert "attribute" in result.content
    assert evidence.rows and evidence.rows[0][1]["success"] is False
