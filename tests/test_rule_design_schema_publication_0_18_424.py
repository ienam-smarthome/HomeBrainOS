"""Regression for source-scoped native Rule Machine proposal publication."""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from rule_design_claim_guard import calibrate_rule_design_review

REQUEST = (
    "Review the supplied native Rule Machine v5.1.6 dated-trigger runbook "
    "without executing it. Validate the one-time trigger contract and safe "
    "log-only action. Report readiness and technical JSON. Do not create, "
    "modify, delete, clone or execute rules or devices."
)
MODEL = """**Read-only rule design review — no automation or device was changed.**

### 1. Upstream-Tested Facts (Contract Validation)
* **Field Types:** time# / atTime# must be HH:mm; date# / atDate# must be MM/dd/yyyy.
* **Year Handling:** current year or daily recurrence inferred.
* **Action Structure:** runCommand with log capability.

### 2. Installed-Hub Observations
* **Timezone:** Europe/London inferred from Octopus Energy apps.

### 3. Unresolved Requirements
A partial create should be checked.

### 4. Readiness Assessment
The plan is **READY** for an isolated log-only test.

**Technical JSON (Proposed Payload):**
```json
{"operation":"create","parent_id":169,"args":{"addTrigger":{"atTime":"12:00","atDate":"12/25/2026"},"addAction":{"capability":"runCommand"}},"confirm":false}
```

### Post-Execution Verification Plan
Read returned rule_id and scheduled jobs.
"""


def receipt(tool, args, *, sub_tool=None):
    return {
        "success": True, "mutates": False, "effect": "read",
        "tool": tool, "sub_tool": sub_tool,
        "arguments": ({"tool": sub_tool, "args": args} if sub_tool else args),
        "evidence_kind": "tool_result",
        "summary": "object fields: apps, count, content",
    }


RECEIPTS = [
    receipt("hub_read_apps_code", {"scope": "instances"}, sub_tool="hub_list_apps"),
    receipt("hub_get_tool_guide", {"section": "set_rule_reference"}),
    receipt("hub_get_tool_guide", {"section": "best_practice_reference"}),
    receipt("hub_read_apps_code", {"scope": "instances"}, sub_tool="hub_list_apps"),
]


def test_live_schema_invention_ready_claim_and_payload_are_withheld():
    answer = calibrate_rule_design_review(MODEL, RECEIPTS, request=REQUEST)
    assert "### Native authoring schema — unverified" in answer
    assert "HH:mm" not in answer
    assert "MM/dd/yyyy" not in answer
    assert "runCommand" not in answer
    assert "### Readiness assessment — unverified" in answer
    assert "The plan is **READY**" not in answer
    assert '"operation":"create"' not in answer
    assert "addTrigger" not in answer
    assert "### Post-Execution Verification Plan" in answer
    assert "### Installed-hub evidence — limited to recorded reads" in answer
    assert "no targeted device" in answer
    assert "### Rule design feasibility gate (read-only)" in answer
    assert "23:00" not in answer
    assert "manual-off lockout" not in answer
    assert "motion active" not in answer
    assert calibrate_rule_design_review(answer, RECEIPTS, request=REQUEST) == answer


def test_unverified_native_json_outside_readiness_section_is_not_exposed():
    answer = calibrate_rule_design_review(
        'Proposed direct command:\n```json\n'
        '{"operation":"create","args":{"changes":[{"part":"trigger"}]}}\n'
        '```\n',
        RECEIPTS, request=REQUEST,
    )
    assert '"operation":"create"' not in answer
    assert "Native write JSON withheld" in answer


def test_motion_request_preserves_specific_duration_safety_warning():
    request = ("Read-only design: Livingroom Light 1 off after 10 minutes "
               "inactive, motion active cancels, within 23:00 to 06:00, "
               "manual-off lockout safe.")
    answer = calibrate_rule_design_review("Proposal only.", RECEIPTS, request=request)
    assert "Wait for Event: motion active" in answer
    assert "23:00" in answer
    assert "manual-off lockout" in answer


def test_source_receipt_discriminates_targeted_from_inventory():
    targeted = RECEIPTS + [
        receipt("hub_read_devices", {"deviceId": "7805"}, sub_tool="hub_get_device"),
        receipt("hub_read_apps_code", {"appId": "4019"}, sub_tool="hub_get_app_config"),
    ]
    answer = calibrate_rule_design_review(
        "Read-only proposal.", targeted,
        request="Review a read-only native scheduling rule design.",
    )
    assert "Targeted device and app configuration reads were recorded" in answer
    assert "limited to recorded reads" not in answer


def test_positive_typed_complete_contract_keeps_existing_answer():
    attested = RECEIPTS + [{
        "success": True,
        "evidence_kind": "typed_native_rule_design_schema",
        "details": {"completeCombinedSemanticsVerified": True},
    }]
    assert calibrate_rule_design_review(
        "Read-only assessment: source-attested native schema.",
        attested, request=REQUEST,
    ) == "Read-only assessment: source-attested native schema."
