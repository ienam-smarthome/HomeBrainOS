"""Phase B adapters / first Phase C read planner acceptance tests.

Only sanitized synthetic typed receipts and the original October replay. No
live MCP calls, no Hubitat mutations, no model-specific keyword routing.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from mcp_client import MCPTool
from investigation_v2 import build_case_file
from investigation_v2.planning import review_model_read_proposals

FIXTURE = Path(__file__).parent / "fixtures" / "investigation_v2_overnight.json"


def config_receipt(**changes):
    row = {
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
        "success": True, "mutates": False, "effect": "read",
        "evidence_kind": "typed_existing_rule_partial_settings",
        "timestamp": "2026-10-25T10:00:00+00:00",
        "arguments": {"tool": "hub_get_app_config",
                      "args": {"appId": "4019", "includeSettings": True}},
        "details": {
            "appId": "4019", "settingsReadable": True,
            "settingsTruncated": False, "orderedActionsValidated": False,
            "controllerFields": [
                {"key": "inactiveAction", "value": "off"},
                {"key": "inactiveOffDelaySeconds", "numericValue": 30,
                 "unitFromKey": "seconds"},
                {"key": "password", "value": "PRIVATE_PASS"},
            ],
            "indexedFields": [{"key": "onOffSwitch.5", "deviceIds": ["7805"]}],
            "secretSettings": {"apiToken": "PRIVATE_TOKEN"},
        },
    }
    row.update(changes)
    return row


def synthetic_execution():
    return {
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_app_execution",
        "success": True, "mutates": False, "effect": "read",
        "evidence_kind": "typed_app_execution",
        "arguments": {"tool": "hub_get_app_execution", "args": {"appId": "4019"}},
        "details": {"executionEvents": [
            {"appId": "4019", "deviceId": "7805", "action": "timerFired",
             "executionObserved": True, "date": "2026-10-25T00:41:00+01:00"},
        ]},
    }


def synthetic_ack():
    return {
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_command_status",
        "success": True, "mutates": False, "effect": "read",
        "evidence_kind": "typed_transport_ack",
        "arguments": {"tool": "hub_get_command_status", "args": {"deviceId": "7805"}},
        "details": {"acknowledgements": [
            {"deviceId": "7805", "commandId": "ack_4019_01", "acknowledged": True,
             "date": "2026-10-25T00:41:01+01:00"},
        ]},
    }


def fixture_case():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return build_case_file(raw["question"], raw["receipts"])


def test_current_stored_config_has_precise_values_not_effective_historical_logic():
    case = build_case_file("Check automation", [config_receipt()])
    assert [(x.stage, x.action, x.value) for x in case.records] == [
        ("config_stored", "stored-setting:inactiveAction", "off"),
        ("config_stored", "stored-setting:inactiveOffDelaySeconds", "30 seconds"),
        ("config_stored", "stored-setting:onOffSwitch.5", "device IDs: 7805"),
    ] or set((x.stage, x.action, x.value) for x in case.records) == {
        ("config_stored", "stored-setting:inactiveAction", "off"),
        ("config_stored", "stored-setting:inactiveOffDelaySeconds", "30 seconds"),
        ("config_stored", "stored-setting:onOffSwitch.5", "device IDs: 7805"),
    }
    assert all(e.target_id == "4019" and e.time_basis == "read_observed_at" for e in case.records)
    assert "PRIVATE_PASS" not in json.dumps(case.to_dict())
    assert "PRIVATE_TOKEN" not in json.dumps(case.to_dict())
    assert "not verified historical" in case.evidence_brief()
    assert not any(e.stage == "app_execution_observed" for e in case.records)


@pytest.mark.parametrize("modification", [
    {"success": False}, {"mutates": True}, {"effect": "write"},
    {"evidence_kind": "unreviewed_config"},
])
def test_no_promotion_from_unsafe_or_unreviewed_config(modification):
    case = build_case_file("Check", [config_receipt(**modification)])
    assert case.records == []


def test_no_typed_config_without_matched_app_id_or_observation_clock():
    wrong = config_receipt()
    wrong["details"]["appId"] = "9999"
    case = build_case_file("Check", [wrong])
    assert not case.records
    assert any("ID-matched" in err for err in case.errors)
    missing_time = config_receipt()
    missing_time.pop("timestamp")
    case = build_case_file("Check", [missing_time])
    assert not case.records
    assert any("missing offset" in err for err in case.errors)


def test_execution_is_separate_from_app_log_and_device_state():
    log = {"tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
           "success": True, "arguments": {"args": {"appId": "4019"}},
           "details": {"logs": [{"name": "off", "date": "2026-10-25T00:40:59+01:00",
                                  "message": "Action: Off"}]}}
    case = build_case_file("Check", [synthetic_execution(), log])
    assert [e.stage for e in case.records] == [
        "app_log_statement", "app_execution_observed"
    ]
    exec_row = case.records[1]
    assert exec_row.producer_id == "4019" and exec_row.target_id == "7805"
    assert not any(e.stage in ("state_reported", "command_issued") for e in case.records)


def test_execution_requires_matching_id_explicitly_confirmed_and_read_only():
    row = synthetic_execution()
    row["details"]["executionEvents"].extend([
        {"appId": "9000", "deviceId": "7805", "action": "off",
         "executionObserved": True, "date": "2026-10-25T00:41:05+01:00"},
        {"appId": "4019", "deviceId": "7805", "action": "off",
         "date": "2026-10-25T00:41:06+01:00"},
    ])
    case = build_case_file("Check", [row])
    assert len(case.records) == 1
    assert any("unverified" in err for err in case.errors)
    row["mutates"] = True
    assert not build_case_file("Check", [row]).records


def test_ack_never_becomes_physical_execution():
    case = build_case_file("Check", [synthetic_ack()])
    assert len(case.records) == 1
    assert case.records[0].stage == "transport_ack"
    assert case.records[0].value == "ack_4019_01"
    assert not any(e.stage == "state_reported" for e in case.records)


def test_ack_requires_matching_device_and_positive_ack():
    row = synthetic_ack()
    row["details"]["acknowledgements"].extend([
        {"deviceId": "8000", "commandId": "bad", "acknowledged": True,
         "date": "2026-10-25T00:41:02Z"},
        {"deviceId": "7805", "commandId": "not-accepted", "acknowledged": False,
         "date": "2026-10-25T00:41:03Z"},
    ])
    case = build_case_file("Check", [row])
    assert len(case.records) == 1
    assert len(case.errors) == 2


def tools():
    return [
        MCPTool("hub_read_devices", "Read devices", {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "enum": ["hub_list_device_events", "hub_get_device"]},
                "args": {"type": "object", "properties": {
                    "deviceId": {"type": "string"},
                    "attribute": {"type": "string"},
                    "hoursBack": {"type": "integer"},
                    "limit": {"type": "integer"},
                }, "required": ["deviceId"], "additionalProperties": False},
            },
            "required": ["tool", "args"], "additionalProperties": False,
        }, annotations={"readOnlyHint": True}),
        MCPTool("hub_manage_rule_machine", "Rule manager", {
            "type": "object", "properties": {
                "tool": {"type": "string", "enum": ["hub_get_rule", "hub_set_rule"]}
            }}),
    ]


def proposal(*, operation="hub_list_device_events", target="7805", hours=24,
             attribute="switch", discriminator="Did the state change?",
             gain="Independent state transitions distinguish dispatch from outcome."):
    return {
        "tool": "hub_read_devices",
        "arguments": {"tool": operation,
                      "args": {"deviceId": target, "attribute": attribute,
                               "hoursBack": hours, "limit": 50}},
        "discriminator": discriminator,
        "information_gain": gain,
        "hypothesis_ids": ["h1", "h2"],
    }


def reviewed(proposals, **kwargs):
    return review_model_read_proposals(
        fixture_case(), proposals, tools(), verified_entity_ids={"7805"},
        **kwargs)


def test_model_proposal_needs_independent_discriminator_and_manifest():
    result = reviewed([proposal()])
    assert len(result.approved) == 1
    assert result.approved[0].hypothesis_ids == ("h1", "h2")
    assert result.budget_remaining == 2
    assert not result.rejected


def test_reject_hallucinated_tool_and_write_even_when_subtool_name_sounds_readonly():
    bad = proposal()
    bad["tool"] = "invented_mcp"
    manager = proposal()
    manager["tool"] = "hub_manage_rule_machine"
    manager["arguments"] = {"tool": "hub_get_rule", "args": {"deviceId": "7805"}}
    output = reviewed([bad, manager])
    assert not output.approved and len(output.rejected) == 2


def test_read_named_gateway_cannot_smuggle_write_operation_or_confirm():
    write = proposal(operation="hub_set_rule")
    confirm = proposal()
    confirm["arguments"]["args"]["confirm"] = True
    output = reviewed([write, confirm])
    assert not output.approved and len(output.rejected) == 2


def test_reject_unadvertised_sub_operation_and_wrong_gateway():
    result = reviewed([proposal(operation="hub_get_undeclared_operation")])
    assert not result.approved
    assert "manifest/discovery" in result.rejected[0].reason


def test_reject_model_invented_target_even_when_schema_valid():
    result = reviewed([proposal(target="9999")])
    assert not result.approved and "verified scope" in result.rejected[0].reason


def test_reject_same_tool_call_and_same_discriminator_across_batch():
    repeated = proposal()
    other = proposal(hours=12)
    output = reviewed([repeated, repeated, other])
    assert len(output.approved) == 1
    assert [e.reason for e in output.rejected] == [
        "duplicate read or discriminator", "duplicate read or discriminator"]


def test_allow_different_discriminator_and_non_duplicate_read():
    output = reviewed([proposal(),
                       proposal(attribute="level", discriminator="Was brightness adjusted?")])
    assert len(output.approved) == 2


def test_reject_prior_exact_read_and_enforce_total_round_budget():
    p = proposal()
    output = reviewed([p], previous_calls=[(p["tool"], p["arguments"])])
    assert not output.approved
    assert "duplicate" in output.rejected[0].reason
    exhausted = reviewed([p], max_total_reads=1)
    assert not exhausted.approved
    assert exhausted.rejected[0].reason == "read budget exhausted"


def test_native_truncated_history_growth_stops_if_limit_does_not_change():
    case = fixture_case()
    output = review_model_read_proposals(
        case, [proposal(hours=168)], tools(), verified_entity_ids={"7805"})
    assert not output.approved
    assert "same capped history" in output.rejected[0].reason
    candidate = proposal(hours=168)
    candidate["arguments"]["args"]["limit"] = 200
    output = review_model_read_proposals(
        case, [candidate], tools(), verified_entity_ids={"7805"})
    assert len(output.approved) == 1


def test_unrelated_question_does_not_change_planner_permission_decision():
    original = fixture_case()
    another = build_case_file("Why did the MQTT watchdog fail?", [])
    p = proposal()
    one = review_model_read_proposals(original, [p], tools(), verified_entity_ids={"7805"})
    two = review_model_read_proposals(another, [p], tools(), verified_entity_ids={"7805"})
    assert len(one.approved) == len(two.approved) == 1
