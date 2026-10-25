"""0.18.118: stored-logic uncertainty must never erase observed runtime proof.

Replays target-matched pieces of the 2026-10-25 v0.18.117 HomeBrain
inspection. All source/command/handler observations are typed, read-only;
none imply an independently verified compiled action tree or physical vacancy.
"""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from existing_rule_claim_guard import calibrate_existing_rule_verification
from api_response_builder import build_agent_response


def _receipt(tool, sub_tool=None, kind=None, details=None, arguments=None):
    return {
        "tool": tool, "sub_tool": sub_tool,
        "evidence_kind": kind, "success": True,
        "effect": "read", "mutates": False,
        "details": details or {}, "arguments": arguments or {},
    }


def _event(name, when, *, value=None, app=None, triggered=None):
    event = {
        "name": name, "value": value,
        "date": f"2026-10-25T{when}+0000",
    }
    if app:
        event["producedBy"] = {"type": "app", "id": app}
    if triggered is not None:
        event["triggered"] = [{"appId": aid, "handler": "motionHandler"} for aid in triggered]
    return event


def _receipts(app="4019"):
    rows = [
        _receipt(
            "hub_read_rules", "hub_get_rule_health", "native_rule_evidence",
            {"appId": app, "verifiedHealth": {"stopped": False}},
            {"tool": "hub_get_rule_health", "args": {"appId": app}},
        ),
        _receipt(
            "hub_read_rules", "hub_list_rule_local_variables", "native_rule_evidence",
            {"appId": app, "returnedVariableCount": 0},
            {"tool": "hub_list_rule_local_variables", "args": {"appId": app}},
        ),
        _receipt(
            "hub_read_apps_code", "hub_get_app_config",
            "typed_existing_rule_partial_settings",
            {
                "appId": app, "settingsReadable": True,
                "controllerFields": [
                    {"key": "backupOffEnabled", "value": True},
                    {"key": "inactiveAction", "value": "off"},
                    {"key": "motionOffLockoutMinutes", "numericValue": 300,
                     "unitFromKey": "minutes"},
                ],
                "orderedActionsValidated": False,
            },
            {"tool": "hub_get_app_config", "args": {"appId": app}},
        ),
        _receipt(
            "homebrain_device_history", kind="deterministic_device_event_history",
            details={
                "label": "Livingroom Light 1", "attribute": "switch",
                "boundaryEvents": [
                    _event("command-off", "16:58:58.691", app=app),
                    _event("switch", "16:58:58.937", value="off"),
                    _event("command-off", "17:01:16.922", app=app),
                    _event("switch", "17:01:17.095", value="off"),
                ],
            },
        ),
        _receipt(
            "homebrain_device_history", kind="deterministic_device_event_history",
            details={
                "label": "FP400 motion sensor", "attribute": "motion",
                "boundaryEvents": [
                    _event("motion", "16:58:28.633", value="inactive",
                           triggered=[int(app)]),
                    _event("motion", "17:00:40.144", value="inactive",
                           triggered=[int(app)]),
                ],
            },
        ),
        _receipt(
            "homebrain_device_history", kind="deterministic_device_event_history",
            details={
                "label": "Matter LWR01 Livingroom Occupancy", "attribute": "motion",
                "boundaryEvents": [
                    _event("motion", "16:58:11.413", value="inactive",
                           triggered=[int(app)]),
                    _event("motion", "17:00:46.653", value="inactive",
                           triggered=[int(app)]),
                ],
            },
        ),
        _receipt(
            "homebrain_device_history", kind="deterministic_device_event_history",
            details={
                "label": "Livingroom Soft Sensor", "attribute": "motion",
                "boundaryEvents": [
                    _event("motion", "16:58:29.649", value="inactive",
                           triggered=[4129]),
                    _event("motion", "17:00:41.163", value="inactive",
                           triggered=[4129]),
                ],
            },
        ),
        _receipt(
            "hub_read_diagnostics", "hub_get_logs", "tool_result",
            {
                "logCount": 3, "logs": [{
                    "date": "2026-10-25 16:18:42.628", "level": "WARN",
                    "message": (
                        f"app|{app}|Livingroom Light 1|method motionHandler "
                        "of app Livingroom Light 1 ran for 129,544ms"
                    ),
                }],
            },
            {"tool": "hub_get_logs", "args": {"appId": app, "limit": 100}},
        ),
        _receipt(
            "homebrain_read_groovy_source", kind="groovy_source_investigation_evidence",
            details={
                "sourceRetrieved": True, "fullImplementationVerified": True,
                "sourceCodeId": "1453", "verifiedCharacters": 186457,
                "declaredTotalCharacters": 186457, "verifiedPages": 4,
            }, arguments={"appId": app, "symbols": ["inactiveAction"]},
        ),
    ]
    return rows


def _coverage():
    return {
        "domain": "existing_rule_verification",
        "status": "partial-evidence",
        "requirements": [
            {"key": "stored_logic", "state": "checked-unverified"},
            {"key": "health", "state": "observed"},
        ],
    }


def test_verified_off_provenance_is_not_renamed_to_missing_runtime_evidence():
    output = calibrate_existing_rule_verification(
        "The app's OFF commands were observed", _receipts(), _coverage(),
        request="Read-only verification of app 4019",
    )
    assert "### Verified observed execution and source coverage" in output
    assert "16:58:58.691" in output
    assert "17:01:16.922" in output
    assert "0.246s later" in output
    assert "0.173s later" in output
    assert "FP400 motion sensor reported inactive at 16:58:28.633" in output
    assert "Matter LWR01 Livingroom Occupancy reported inactive at 17:00:46.653" in output
    assert "30.058s later" in output
    assert "30.269s later" in output
    assert "Livingroom Soft Sensor" not in output
    assert "- Runtime triggering, delay cancellation and actual OFF commands." not in output
    assert "Other runtime trigger branches" in output
    assert "ordered actions" in output


def test_handler_warn_and_complete_source_must_survive_partial_logic_gate():
    output = calibrate_existing_rule_verification(
        "Generic partial summary", _receipts(), _coverage(),
        request="read-only verify app 4019",
    )
    assert "129,544ms (129.544s)" in output
    assert "motionHandler" in output
    assert "16:18:42.628" in output
    assert "all 186,457 characters were retrieved" in output
    assert "code 1453" in output
    assert "does not independently validate" in output
    assert "not independent proof" in output
    assert "motionOffLockoutMinutes=300" in output
    assert "not their position" in output


def test_non_target_receipts_do_not_leak_into_audit():
    rows = _receipts()
    extra = _receipts(app="9020")
    # Bring only non-target runtime events; do not add 9020 rule-health evidence.
    rows += extra[3:]
    text = calibrate_existing_rule_verification(
        "Partial", rows, _coverage(), request="verify app 4019",
    )
    assert "App 9020 issued" not in text
    assert "App 9020 native WARN" not in text
    assert "App 9020 installed Groovy" not in text


def test_no_new_unsupported_proof_when_no_runtime_history():
    rows = _receipts()[:3]
    text = calibrate_existing_rule_verification(
        "Partial", rows, _coverage(), request="verify app 4019",
    )
    assert "Verified observed execution and source coverage" not in text
    assert "- Runtime triggering, delay cancellation and actual OFF commands." in text


def test_generic_app_id_not_special_cased():
    text = calibrate_existing_rule_verification(
        "Partial", _receipts(app="9020"), _coverage(),
        request="verify app 9020",
    )
    assert "App 9020 issued OFF" in text
    assert "App 9020 native WARN" in text
    assert "App 9020 installed Groovy" in text
    assert "30.058s later" in text


def test_api_response_retains_positive_evidence_and_unresolved_flag():
    outcome = SimpleNamespace(
        message="The rule status is unknown.",
        request_class="live-read", route="unified-mcp-agent",
        evidence=_receipts(), metrics={
            "outcome": "unresolved", "counters": {},
            "timings_ms": {},
        },
        investigation_coverage=_coverage(),
    )
    # The orchestrator applies the rule report before API serialization.
    synthesized = calibrate_existing_rule_verification(
        outcome.message, outcome.evidence, outcome.investigation_coverage,
        request="verify app 4019",
    )
    outcome.message = synthesized
    response = build_agent_response(outcome, model="gemma4:31b",
                                    elapsed_ms=60000, version="0.18.118")
    assert response["outcome_presentation"]["value"] == "unresolved"
    assert "30.058s later" in response["message"]
    assert "129,544ms" in response["message"]
    assert "186,457 characters" in response["message"]
    assert response["evidence"] == outcome.evidence
