"""v0.18.75 editor-page read diagnostics: never claim a compiled action tree."""
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


def config(paragraphs):
    return {
        "success": True,
        "app": {"id": "4246", "type": "Rule-5.1"},
        "page": {"name": "selectActions", "sections": [
            {"title": "Actions", "paragraphs": paragraphs, "inputs": []}
        ]},
        "settings": {"secretPassword": "SECRET_DO_NOT_LEAK"},
    }


@pytest.mark.parametrize("paragraphs,types", [
    ([
        "1. Cancel Delayed Actions",
        "2) IF (FP400 inactive and light is ON)",
        "Action 3: Delay 0:10:00 (cancelable)",
        "4: IF (FP400 inactive)",
        "5. Off: Livingroom Light 1",
        "6. END-IF",
        "7. END-IF",
    ], ["cancel-delayed-actions", "if", "delay", "if", "off", "end-if", "end-if"]),
    ([
        "• Cancel Delayed Actions",
        "Step 2: IF (motion inactive)",
        "* Delay 00:10:00",
        "Action: Off: Livingroom Light 1",
    ], ["cancel-delayed-actions", "if", "delay", "off"]),
    (["<span>1. Cancel Delayed Actions</span>", "<div>2. IF (motion inactive)</div>"],
     ["cancel-delayed-actions", "if"]),
])
def test_safe_common_page_numbering_types_without_releasing_labels(paragraphs, types):
    projected = project_existing_rule_page(config(paragraphs), "4246", "selectActions")
    assert [r["kind"] for r in projected["recognizedActionRows"]] == types
    assert projected["orderedActionsValidated"] is False
    assert projected["conditionsValidated"] is False
    for sensitive in ["FP400", "Livingroom", "SECRET_DO_NOT_LEAK"]:
        assert sensitive not in str(projected)


def test_unclassified_live_page_keeps_counts_and_bounded_syntax_hints():
    paras = [
        "Rule builder: Choose an action from a list.",
        "The rendered page mentions Cancel Delayed Actions as a guide.",
        "Step details for IF (motion inactive)",
        "Delay 10 min is a supported option.",
        "To switch Off: Livingroom Light, select an action.",
        "https://secret.invalid?token=SUPER_SECRET",
        "<section>Editor guide section</section>",
        "No recognized action at the start",
    ]
    result = project_existing_rule_page(config(paras), "4246", "selectActions")
    assert result["pageReadVerified"] is True
    assert result["paragraphsInspected"] == 8
    assert result["recognizedActionRows"] == []
    assert result["paragraphSyntaxHints"]["cancel_delayed"] == 1
    assert result["paragraphSyntaxHints"]["conditional_if"] == 1
    assert result["paragraphSyntaxHints"]["delay"] == 1
    assert result["paragraphSyntaxHints"]["switch_off"] == 1
    assert result["paragraphShapeCounts"]["html_markup"] == 1
    for forbidden in ["SUPER_SECRET", "secret.invalid", "Livingroom", "motion inactive"]:
        assert forbidden not in str(result)
    receipt = [{
        "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
        "success": True, "mutates": False, "evidence_kind": "tool_result",
        "arguments": {"tool": "hub_get_app_config",
                      "args": {"appId": "4246", "pageName": "selectActions"}},
        "details": result,
    }]
    plan = plan_investigation(
        "Verify Rule Machine app 4246 persisted ordered actions. "
        "Do not create or modify anything."
    )
    coverage = assess_investigation(plan, receipt)
    message = calibrate_existing_rule_verification(
        "Everything is verified.", receipt, coverage,
    )
    assert "8 paragraphs inspected" in message
    assert "cancel_delayed=1" in message
    assert "html_markup=1" in message
    assert "not validated action rows" in message
    assert coverage["evidenceComplete"] is False
    for secret in ["SUPER_SECRET", "Livingroom Light", "Everything is verified"]:
        assert secret not in message


@pytest.mark.parametrize("paragraph", [
    "Help: to use Cancel Delayed Actions choose it from the dropdown.",
    "You may configure an IF (expression) after a delay.",
    "Please click Off: Livingroom Light 1 to continue.",
    "https://user:password@private.example/Danger",
    "Action: On: secret\nnext line",
])
def test_prose_mentions_not_promoted_to_actions(paragraph):
    p = project_existing_rule_page(config([paragraph]), "4246", "selectActions")
    assert p["recognizedActionRows"] == []
    assert p["orderedActionsValidated"] is False


def test_wrong_app_or_page_never_gets_diagnostic_observations():
    p = config(["Action: Delay 0:10:00"])
    bad_id = project_existing_rule_page(p, "4019", "selectActions")
    bad_page = project_existing_rule_page(p, "4246", "selectTriggers")
    assert not bad_id["pageReadVerified"]
    assert not bad_page["pageReadVerified"]
    assert all(v == 0 for v in bad_id["paragraphSyntaxHints"].values())
    assert not bad_id["recognizedActionRows"]


def test_limit_labels_and_oversize_not_leaked():
    rows = ["1. Off: PRIVATE_DEVICE"] * 42 + ["https://secret.invalid/?pw=X" * 50]
    p = project_existing_rule_page(config(rows), "4246", "selectActions")
    assert p["pageRowsTruncated"] is True
    assert len(p["recognizedActionRows"]) == 40
    assert "PRIVATE_DEVICE" not in str(p)
    assert "secret.invalid" not in str(p)
