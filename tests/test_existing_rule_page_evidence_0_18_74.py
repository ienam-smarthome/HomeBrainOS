"""v0.18.74: evidence from actual Rule Machine editor pages survives synthesis.

Page observations are a bounded *rendered text* projection, not a native
actionList or authoritative condition topology.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from existing_rule_page_evidence import (
    existing_rule_page_metadata, project_existing_rule_page,
)
from existing_rule_claim_guard import calibrate_existing_rule_verification
from investigation_intelligence import plan_investigation, assess_investigation


def page(app="4246", name="selectActions"):
    return {
        "success": True,
        "app": {"id": int(app), "type": "Rule-5.1"},
        "page": {
            "name": name,
            "sections": [
                {"title": "Actions to Run", "paragraphs": [
                    "Action: Cancel Delayed Actions",
                    "Action: IF (FP400 motion sensor motion is inactive AND "
                    "Livingroom Light 1 on AND time between 23:00 and 06:00)",
                    "Action: Delay 0:10:00 (cancelable)",
                    "Action: IF (FP400 motion sensor motion is inactive)",
                    "Action: Off: Livingroom Light 1",
                    "Action: END-IF",
                    "Action: END-IF",
                    "Server secret: https://PRIVATE.example/token/SECRET",
                ], "inputs": [
                    {"name": "password", "value": "SECRET_PASSWORD"},
                ]},
            ],
        },
        "settings": {"apiToken": "SECRET_API_KEY"},
    }


def test_source_qualified_partial_action_rows_preserve_syntax_not_labels():
    report = project_existing_rule_page(page(), "4246", "selectActions")
    assert report["pageReadVerified"] is True
    assert report["recognizedActionRows"] == [
        {"kind": "cancel-delayed-actions"},
        {"kind": "if"},
        {"kind": "delay", "seconds": 600, "cancelable": True},
        {"kind": "if"},
        {"kind": "off"},
        {"kind": "end-if"},
        {"kind": "end-if"},
    ]
    assert report["orderedActionsValidated"] is False
    assert report["conditionsValidated"] is False
    assert report["triggerLogicValidated"] is False
    for value in ("Livingroom Light", "FP400", "PRIVATE", "SECRET", "password",
                  "https://", "23:00"):
        assert value not in str(report)


def test_different_expected_id_or_page_rejected_even_when_content_looks_valid():
    wrong_id = project_existing_rule_page(page(), "4019", "selectActions")
    wrong_page = project_existing_rule_page(page(), "4246", "selectTriggers")
    assert wrong_id["pageReadVerified"] is False
    assert wrong_page["pageReadVerified"] is False
    assert not wrong_id["recognizedActionRows"]
    assert not wrong_page["recognizedActionRows"]


@pytest.mark.parametrize("invalid", [
    {"success": False, **page()},
    {"app": {"id": "4246"}, "page": {"sections": {}}},
    {"app": {"id": "4246"}, "page": {"sections": "not a list"}},
    {"app": {"id": "4246"}, "page": []},
    {"success": True, "app": {"id": "9999"}, "page": {"sections": []}},
])
def test_malformed_page_cannot_promote_semantics(invalid):
    if "success" in invalid and invalid["success"] is False:
        invalid["success"] = False
    result = project_existing_rule_page(invalid, "4246", "selectActions")
    assert result["pageReadVerified"] is False
    assert result["orderedActionsValidated"] is False


def test_tool_gateway_enforces_exact_scope_and_supported_pages():
    scoped = existing_rule_page_metadata("hub_read_apps_code", {
        "tool": "hub_get_app_config",
        "args": {"appId": "4246", "pageName": "selectActions"},
    }, page())
    assert scoped["recognizedActionRows"][2]["seconds"] == 600
    assert existing_rule_page_metadata("hub_read_apps_code", {
        "tool": "hub_set_rule",
        "args": {"appId": "4246", "pageName": "selectActions"},
    }, page()) is None
    assert existing_rule_page_metadata("hub_read_apps_code", {
        "tool": "hub_get_app_config",
        "args": {"appId": "4246", "pageName": "mainPage"},
    }, page()) is None
    assert existing_rule_page_metadata("hub_read_devices", {
        "tool": "hub_get_app_config",
        "args": {"appId": "4246", "pageName": "selectActions"},
    }, page()) is None


def test_report_keeps_evidence_partial_and_surfaces_displayed_rows():
    args = {"tool": "hub_get_app_config", "args": {
        "appId": "4246", "pageName": "selectActions",
    }}
    details = existing_rule_page_metadata("hub_read_apps_code", args, page())
    evidence = [{
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_get_app_config",
        "success": True,
        "mutates": False,
        "evidence_kind": "tool_result",
        "arguments": args,
        "details": details,
    }]
    plan = plan_investigation(
        "Read-only verify Rule Machine app 4246 ordered actions. "
        "Do not create or modify rules."
    )
    coverage = assess_investigation(plan, evidence)
    assert coverage["evidenceComplete"] is False
    assert {item["key"]: item["state"] for item in coverage["requirements"]}[
        "stored_logic"
    ] == "checked-unverified"
    result = calibrate_existing_rule_verification(
        "The full sequence is verified: SECRET_PASSWORD", evidence, coverage,
    )
    assert "Editor-page observations" in result
    assert "cancel-delayed-actions" in result
    assert "delay 600s (cancelable in page text)" in result
    assert "end-if" in result
    assert "orderedActionsValidated" not in result
    assert "SECRET_PASSWORD" not in result
    assert "may be incomplete" in result
    assert "Investigation remains partial" in result


def test_page_lookups_and_different_apps_are_not_confused():
    report = project_existing_rule_page(page(name="selectTriggers"), "4246", "selectTriggers")
    assert report["pageReadVerified"] is True
    evidence = [{
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_get_app_config",
        "success": True,
        "mutates": False,
        "evidence_kind": "tool_result",
        "arguments": {"tool": "hub_get_app_config", "args": {
            "appId": "4246", "pageName": "selectTriggers",
        }},
        "details": report,
    }]
    coverage = assess_investigation(plan_investigation(
        "Audit existing Rule Machine app 4246 triggers and conditions. "
        "Do not create or modify anything."
    ), evidence)
    message = calibrate_existing_rule_verification("verified", evidence, coverage)
    assert "trigger contents not independently parsed or verified" in message


def test_page_text_limits_and_control_characters():
    long_page = page()
    long_page["page"]["sections"][0]["paragraphs"] += ["On: Light"] * 150
    report = project_existing_rule_page(long_page, "4246", "selectActions")
    assert report["pageRowsTruncated"] is True
    assert len(report["recognizedActionRows"]) <= 40
    for bad in ("Action: Delete all devices", "Action: On: secret\nmulti-line", 
                "Delay 99:99:99", "https://private.example"):
        assert not project_existing_rule_page({
            "app": {"id": "4246"}, "page": {"name": "selectActions", "sections": [
                {"paragraphs": [bad]},
            ]},
        }, "4246", "selectActions")["recognizedActionRows"]
