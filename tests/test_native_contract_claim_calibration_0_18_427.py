"""Evidence-bound native authoring contract publication and readiness.

Regression from the installed v0.18.426 read-only runbook review.  The guide
read succeeded, but no typed dated-trigger contract was independently attested.
No Hubitat operations are performed by these tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from investigation_intelligence import assess_investigation, plan_investigation
from rule_design_claim_guard import calibrate_rule_design_review

REQUEST = (
    "Review the MCP Rule Server v5.1.6 native one-time dated-trigger runbook. "
    "READ-ONLY. Verify documented trigger field types, date/time formats, "
    "year# handling, native log-only action structure, parent ID, backup "
    "prerequisites and scheduler verification. Distinguish upstream-tested "
    "facts, installed-hub evidence and unresolved requirements. "
    "Do not create or modify rules, open native editor forms, or queue "
    "confirmations. Include Technical JSON."
)
KEY = "I-HAVE-READ-THE-GUIDE-set_rule_reference-6de9eb49"


def guide_receipt():
    return {
        "tool": "hub_get_tool_guide", "success": True,
        "effect": "read", "mutates": False,
        "arguments": {"section": "set_rule_reference"},
        "summary": "object fields: success, section, content",
        "evidence_kind": "tool_result",
    }


def sample_answer():
    fence = chr(96) * 3
    return (
        "**Read-only rule design review — no automation changed.**\n\n"
        "**Evidence qualification:** The read receipts did not verify both "
        "targeted device and complete app-configuration sources.\n\n"
        "### Investigation Coverage\n"
        "- **Domain**: rule_design_review\n"
        "- **Evidence Complete**: Partial. General structural contracts "
        "are verified.\n"
        "- **Readiness for Mutation**: NOT READY\n\n"
        "### Typed Authoring Contract Review\n"
        "| Requirement | Status | Evidence / Finding | Source |\n"
        "| --- | --- | --- | --- |\n"
        "| **Trigger Field Types** | Verified | capability/fields schema | set_rule_reference |\n"
        "| **Date/Time Formats** | Partial | Variables use ISO timestamp | set_rule_reference |\n"
        "| **Year# Handling** | Verified | logmsg.# proves year# | set_rule_reference |\n"
        "| **Log-Only Action** | Verified | getLogMsg action | set_rule_reference |\n"
        "| **Parent ID** | Verified | Required for create | set_rule_reference |\n"
        "| **Backup Prereqs** | Verified | Recent backup required | best_practice |\n"
        "| **Scheduler Verif.** | Partial | Healthy rule implies scheduled | set_rule_reference |\n\n"
        "### Analysis of Evidence\n"
        "- **Upstream-Tested Facts**: The JSON fields were verified upstream.\n"
        "- **Installed-Hub Evidence**: None retrieved.\n\n"
        "### Technical JSON (Contract Projection)\n"
        + fence + "json\n"
        + json.dumps({"authoring_contract": {
            "write_requirements": {"acknowledgment_key": KEY},
            "structural_types": {
                "trigger": {"capability": "string", "fields": []},
            },
        }}, indent=2)
        + "\n" + fence + "\n\n"
        "### Rule design feasibility gate (read-only)\n"
        "Native creation is unverified; inspect targeted device rules.\n"
    )


def test_live_guide_only_review_does_not_publish_verified_native_fields():
    answer = calibrate_rule_design_review(
        sample_answer(), [guide_receipt()], request=REQUEST,
    )
    assert "Typed Authoring Contract Review" in answer
    assert "| Verified |" not in answer
    assert "| Not source-verified |" in answer
    assert "| Unverified |" in answer
    assert "logmsg.# proves year#" not in answer
    assert "Variables use ISO timestamp" not in answer
    assert "Healthy rule implies scheduled" not in answer
    assert "upstream integration tests" in answer
    assert "General structural contracts are verified" not in answer
    assert "native authoring-contract review" in answer
    assert "targeted device and complete app-configuration" not in answer
    assert "inspect targeted device rules" not in answer
    assert "readinessForMutation=false" in answer
    assert "redacted-guide-key" not in answer  # projection is removed
    assert KEY not in answer
    assert '"authoring_contract"' not in answer
    assert '"typed_authoring_contract": "checked-unverified"' in answer
    assert '"readinessForMutation": false' in answer


def test_guide_key_redaction_does_not_strip_non_contract_diagnostic_json():
    fence = chr(96) * 3
    text = "### Note\n" + fence + "json\n" + (
        '{"checked":true,"key":"' + KEY + '"}'
    ) + "\n" + fence
    answer = calibrate_rule_design_review(text, [guide_receipt()], request=REQUEST)
    assert KEY not in answer
    assert "[redacted-guide-key]" in answer
    assert '"checked":true' in answer


def test_actual_typed_schema_attestation_preserves_independent_findings():
    typed = {
        "tool": "homebrain_authoring_schema", "success": True,
        "mutates": False, "effect": "read",
        "evidence_kind": "typed_native_rule_design_schema",
        "details": {"completeCombinedSemanticsVerified": True},
    }
    evidence = "### Typed Authoring Contract Review\n| Field | Status | Source |\n|---|---|---|\n| data | Verified | typed |"
    answer = calibrate_rule_design_review(
        evidence + "\nKey: " + KEY, [typed], request=REQUEST,
    )
    assert "| data | Verified | typed |" in answer
    assert KEY not in answer
    assert "[redacted-guide-key]" in answer


def test_review_coverage_reports_false_mutation_readiness_for_guide_only():
    plan = plan_investigation(REQUEST)
    assert plan is not None
    assert plan.domain == "rule_design_review"
    coverage = assess_investigation(plan, [guide_receipt()])
    assert coverage["evidenceComplete"] is False
    assert coverage["readinessForMutation"] is False
    states = {r["key"]: r["state"] for r in coverage["requirements"]}
    assert states["typed_authoring_contract"] == "checked-unverified"


def test_even_typed_review_completion_is_not_write_authorisation():
    plan = plan_investigation(REQUEST)
    assert plan is not None
    coverage = assess_investigation(plan, [
        guide_receipt(),
        {
            "success": True, "mutates": False, "effect": "read",
            "tool": "native_schema", "evidence_kind": "typed_native_rule_design_schema",
            "details": {"completeCombinedSemanticsVerified": True},
        },
    ])
    assert coverage["readinessForMutation"] is False
    states = {r["key"]: r["state"] for r in coverage["requirements"]}
    assert states["typed_authoring_contract"] == "observed"


def test_unrelated_rule_design_keeps_its_existing_warning_scope():
    answer = calibrate_rule_design_review(
        "Design only.", [], request=(
            "Read-only: design a motion rule to turn a light off after ten "
            "minutes inactive from 23:00 to 06:00. Do not create it."
        ),
    )
    assert "Wait for Event: motion active" in answer
    assert "23:00" in answer
