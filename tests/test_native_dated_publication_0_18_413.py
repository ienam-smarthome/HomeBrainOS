"""Installed 0.18.412 failure: typed date scan survived completion, but not
the earlier generic existing-rule calibrator. Regress both publication stages.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from evidence_recorder import EvidenceRecorder
from mcp_client import MCPToolResult
from mcp_agent_orchestrator import AgentOutcome
from existing_rule_claim_guard import calibrate_existing_rule_verification
from native_dated_trigger_discovery import (
    read_existing_dated_triggers,
    existing_dated_trigger_coverage,
    is_existing_dated_trigger_question,
)
from shared_investigation_completion import apply_shared_investigation_completion


REQUEST = (
    "Perform a read-only investigation of existing native Rule Machine dated triggers. "
    "Search for an already-existing Rule Machine rule using Certain Time (and optional date). "
    "If one exists, inspect saved native trigger settings time#, atTime#, date# and atDate# "
    "and whether the date is enabled. Use only safe read-only sources. "
    "Do not invoke form-opening operations that may execute app code or cause side effects. "
    "If no suitable existing rule or reliable saved-state source exists, report that limitation. "
    "Do not create a test rule. Compare findings against installed MCP v5.1.5. "
    "Keep authorisation disabled. Include Technical JSON."
)
REAL_SCAN_IDS = (
    1881, 2075, 2084, 2217, 2305, 2706, 2710, 2817,
    2843, 2844, 2967, 3055,
) + tuple(range(3100, 3130))


class FakeLiveReadMCP:
    def __init__(self) -> None:
        self.calls = []

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        leaf = arguments["tool"]
        if leaf == "hub_list_apps":
            data = {
                "apps": [
                    {"id": rid, "name": "Existing RM " + str(rid),
                     "type": "Rule-5.1", "user": False, "parentId": 169}
                    for rid in REAL_SCAN_IDS
                ],
                "count": 42,
                "totalOnHub": 60,
            }
        else:
            assert leaf == "hub_set_rule"
            assert arguments["args"]["operation"] == "read"
            assert arguments["args"]["args"]["sections"] == ["triggers", "settings"]
            rule = arguments["args"]["rule_id"]
            data = {"rule_id": rule, "triggers": {}, "settings": []}
            if rule == 2710:
                data = {
                    "rule_id": 2710,
                    "triggers": {"1": "Certain Time (and optional date)"},
                    "settings": [
                        {"name": "time1", "type": "enum", "value": "A specific time"},
                        {"name": "atTime1", "type": "time", "value": "22:30"},
                        {"name": "date1", "type": "bool", "value": None},
                        {"name": "accessToken", "type": "password", "value": "PRIVATE"},
                    ],
                }
            if rule == 2967:
                data = {"rule_id": 9000, "triggers": {}, "settings": []}
        return MCPToolResult(
            name=gateway, arguments=arguments, raw={},
            text="", data=data, is_error=False,
        )


def _installed_shape():
    mcp = FakeLiveReadMCP()
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        answer, details = asyncio.run(read_existing_dated_triggers(
            mcp, recorder, question=REQUEST,
            available_names=frozenset({
                "hub_read_apps_code", "hub_manage_native_rules_and_apps",
            }),
        ))
        evidence = recorder.receipts()
    finally:
        recorder.reset(token)
    return mcp, answer, details, evidence


def _broad_existing_rule_coverage():
    # Actual v0.18.412 early finalisation used this existing-rule domain.
    return {
        "domain": "existing_rule_verification",
        "status": "partial-evidence",
        "evidenceComplete": False,
        "requirements": [
            {"key": "stored_logic", "state": "checked-unverified"},
            {"key": "health", "state": "checked-unverified"},
        ],
    }


def test_installed_42_candidate_12_read_scan_retains_real_partial_evidence():
    assert is_existing_dated_trigger_question(REQUEST)
    mcp, message, details, evidence = _installed_shape()
    assert len(mcp.calls) == 13
    assert len(evidence) == 14
    assert details["eligibleVisibleNativeRules"] == 42
    assert details["inventoryPagesRead"] == 1
    assert details["inventoryPageTraversalComplete"] is True
    assert details["scanOffset"] == 0
    assert details["scanLimit"] == 12
    assert len(details["scannedRuleIds"]) == 12
    assert [v["ruleId"] for v in details["scannedRuleIds"]] == [
        str(x) for x in REAL_SCAN_IDS[:12]
    ]
    assert details["savedDatedFieldReadbackVerified"] is False
    assert details["absenceProven"] is False
    assert details["moreCandidatesMayExist"] is True
    assert details["readinessForMutation"] is False

    assert "Visible native Rule-5.1 candidates in returned inventory: 42" in message
    assert "attempted native rule reads: 12" in message
    assert "Resume with scan offset 12" in message
    assert "rule 2710" in message
    assert "time=22:30" in message
    assert "date flag=value unverified" in message
    assert "atDate=not returned" in message
    assert "No verified enabled dated-trigger field set" in message
    assert "PRIVATE" not in message
    assert "PRIVATE" not in str(details)
    assert "inactivity" not in message.lower()
    assert "controller interference" not in message.lower()
    assert all(r["mutates"] is False and r["effect"] == "read" for r in evidence)
    assert evidence[11]["success"] is False  # app 2967


def test_early_generic_calibrator_no_longer_overwrites_typed_dated_scan():
    _, message, _, receipts = _installed_shape()
    upstream = _broad_existing_rule_coverage()
    preserved = calibrate_existing_rule_verification(
        message, receipts, upstream, request=REQUEST,
    )
    assert preserved == message
    assert "Read-only existing-rule verification" not in preserved
    assert "nested IF" not in preserved
    assert "inactivity-OFF" not in preserved

    outcome = AgentOutcome(
        message=preserved,
        request_class="live-read",
        evidence=receipts,
        choices=[],
        investigation_coverage=upstream,
    )
    final = apply_shared_investigation_completion(outcome, REQUEST)
    assert final.message == message
    assert final.investigation_coverage["domain"] == "native_dated_trigger_discovery"
    assert final.investigation_coverage["evidenceComplete"] is False
    assert final.investigation_coverage["questionResolved"] is False
    assert final.investigation_coverage["readinessForMutation"] is False
    assert final.metrics["outcome"] == "unresolved"
    assert existing_dated_trigger_coverage(REQUEST, receipts) is not None


def test_generic_existing_rule_audit_still_uses_its_claim_guard():
    question = (
        "Read-only verify existing Rule Machine rule 4163 with "
        "ordered actions, action-tree structure, duplicates and health."
    )
    unverified = _broad_existing_rule_coverage()
    response = calibrate_existing_rule_verification(
        "This rule is completely verified.", [], unverified,
        request=question,
    )
    assert "Read-only existing-rule verification" in response
    assert "Investigation remains partial" in response
    assert "completely verified" not in response


def test_no_typed_dated_source_cannot_exempt_generic_guard():
    source = _broad_existing_rule_coverage()
    only_inventory = [{
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_list_apps",
        "evidence_kind": "tool_result",
        "effect": "read",
        "mutates": False,
        "success": True,
    }]
    guarded = calibrate_existing_rule_verification(
        "No dated rules exist.", only_inventory,
        source, request=REQUEST,
    )
    assert "Read-only existing-rule verification" in guarded
    assert "No dated rules exist" not in guarded
