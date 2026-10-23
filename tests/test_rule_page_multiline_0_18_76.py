"""v0.18.76: recover anchored rendered editor rows inside multiline paragraphs.

The live app 4246 editor response on Oct 23 returned eight paragraphs;
two were multiline and one exceeded 400 characters. Action keywords were
present but the v0.18.75 parser rejected whole paragraphs. These tests use
synthetic structures only (the live raw paragraphs were not retained).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from existing_rule_page_evidence import project_existing_rule_page
from existing_rule_claim_guard import calibrate_existing_rule_verification
from investigation_intelligence import plan_investigation, assess_investigation


def config(paragraphs, app="4246"):
    return {
        "success": True,
        "app": {"id": app, "type": "Rule-5.1"},
        "page": {"name": "selectActions", "sections": [
            {"title": "Actions to Run", "paragraphs": paragraphs, "inputs": []}
        ]},
        "settings": {"authToken": "DO_NOT_EXPOSE"},
    }


def test_eight_paragraphs_multiline_action_lines_preserved_without_raw_text():
    paras = [
        "Actions to Run",
        "Schedule header",
        "The current rule is enabled",
        "1. Cancel Delayed Actions\n"
        "2. IF (FP400 motion inactive AND Livingroom Light 1 is ON)\n"
        "3. Delay 0:10:00 (cancelable)\n"
        "4. IF (FP400 motion inactive)",
        "Some other editor note without a direct action",
        "5. Off: Livingroom Light 1\n"
        "6. END-IF\n"
        "7. END-IF",
        "Z" * 600,  # not promoted to an action or leaked
        "Footer",
    ]
    result = project_existing_rule_page(config(paras), "4246", "selectActions")
    assert result["pageReadVerified"] is True
    assert result["paragraphsInspected"] == 8
    assert result["paragraphShapeCounts"]["multiline"] == 2
    assert result["paragraphShapeCounts"]["over_limit"] == 1
    assert result["paragraphShapeCounts"]["multiline_action_rows"] == 7
    assert [v["kind"] for v in result["recognizedActionRows"]] == [
        "cancel-delayed-actions", "if", "delay", "if", "off", "end-if", "end-if",
    ]
    assert result["recognizedActionRows"][2]["seconds"] == 600
    assert result["recognizedActionRows"][2]["cancelable"] is True
    assert result["orderedActionsValidated"] is False
    assert result["conditionsValidated"] is False
    assert result["triggerLogicValidated"] is False
    assert "Z" * 120 not in str(result)
    for sensitive in ("Livingroom", "FP400", "DO_NOT_EXPOSE"):
        assert sensitive not in str(result)


def test_long_multiline_paragraph_safe_when_physical_lines_bounded():
    paras = [
        "Intro label\n" + "\n".join("Action: Cancel Delayed Actions"
                                   for _ in range(3)) + "\n" + ("A" * 500),
        "Action: IF (PRIVATE_SENSOR motion inactive)\nAction: END-IF",
    ]
    result = project_existing_rule_page(config(paras), "4246", "selectActions")
    assert result["paragraphShapeCounts"]["over_limit"] == 1
    assert len(result["recognizedActionRows"]) == 5
    assert "A" * 50 not in str(result)
    assert "PRIVATE_SENSOR" not in str(result)


@pytest.mark.parametrize("paragraph", [
    "Action: On: admin-secret\nA second line of text",
    "User guide\nIF (example only)",
    "An instruction describing Delay 0:10:00\nDo not execute it",
    "Help: Cancel Delayed Actions\nHelp: Off: your livingroom light",
    "Action: Off: Livingroom Light 1\nThe OFF control is not enabled",
])
def test_lone_action_with_an_arbitrary_extra_line_remains_unverified(paragraph):
    r = project_existing_rule_page(config([paragraph]), "4246", "selectActions")
    assert r["recognizedActionRows"] == []
    assert r["orderedActionsValidated"] is False


def test_oversize_line_not_promoted_even_if_keyword_occurs():
    data = config(["1. IF (" + "private condition" * 70 + ")\n"
                   "2. END-IF"])
    r = project_existing_rule_page(data, "4246", "selectActions")
    assert r["recognizedActionRows"] == []
    assert r["paragraphShapeCounts"]["over_limit"] == 1


@pytest.mark.parametrize("value", [
    "Action: IF (a)\nAction: END-IF\n" + "\n".join("Action: END-IF" for _ in range(50)),
    "Action: IF (a)\nAction: END-IF\n" + ("TOKEN" * 2500),
])
def test_excessive_source_is_bounded_and_fail_closed(value):
    result = project_existing_rule_page(config([value]), "4246", "selectActions")
    assert result["pageRowsTruncated"] is True
    assert result["orderedActionsValidated"] is False
    assert "TOKEN" not in str(result)


def test_final_partial_report_includes_multiline_rows_but_not_certified_topology():
    payload = config(["1. Cancel Delayed Actions\n2. IF (motion inactive)\n"
                      "3. Delay 0:10:00 (cancelable)\n4. END-IF"])
    details = project_existing_rule_page(payload, "4246", "selectActions")
    receipt = [{
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_get_app_config",
        "success": True,
        "mutates": False,
        "effect": "read",
        "evidence_kind": "tool_result",
        "arguments": {
            "tool": "hub_get_app_config",
            "args": {"appId": "4246", "pageName": "selectActions"},
        },
        "details": details,
    }]
    plan = plan_investigation(
        "Verify Rule Machine app 4246 persisted ordered actions and conditions. "
        "Do not create or modify rules."
    )
    assert plan is not None
    coverage = assess_investigation(plan, receipt)
    assert coverage["evidenceComplete"] is False
    msg = calibrate_existing_rule_verification(
        "The complete action tree is verified.", receipt, coverage,
    )
    assert "cancel-delayed-actions" in msg
    assert "delay 600s (cancelable in page text)" in msg
    assert "multiline_action_rows=4" in msg
    assert "complete action tree is verified" not in msg
    assert "may be incomplete" in msg
    assert "Investigation remains partial" in msg


def test_other_app_id_fails_closed():
    r = project_existing_rule_page(
        config(["1. IF (motion)\n2. END-IF"], app="4019"),
        "4246", "selectActions",
    )
    assert not r["pageReadVerified"]
    assert not r["recognizedActionRows"]
