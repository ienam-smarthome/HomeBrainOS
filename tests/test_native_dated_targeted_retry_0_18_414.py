"""Exact-ID native date-field retry cannot turn into arbitrary rule reads/writes."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_client import MCPToolResult
from evidence_recorder import EvidenceRecorder
from mcp_agent_orchestrator import AgentOutcome
from native_dated_trigger_discovery import (
    _requested_rule_ids,
    is_existing_dated_trigger_question,
    read_existing_dated_triggers,
)
from shared_investigation_completion import apply_shared_investigation_completion


REQUEST = (
    "Retry read-only inspection of existing native Rule Machine dated triggers "
    "for rule IDs 2967 and 3985. Check saved time#, atTime#, date# and atDate# "
    "types and values through operation=read only. Do not create, modify, "
    "delete, run or open forms for any rules. Include Technical JSON."
)


def _document(rule_id):
    return {
        "rule_id": rule_id,
        "triggers": {"1": "Certain Time (and optional date)"},
        "settings": [
            {"name": "time1", "type": "enum", "value": "A specific time"},
            {"name": "atTime1", "type": "time", "value": "22:30"},
            {"name": "date1", "type": "bool", "value": None},
        ],
    }


class FakeMCP:
    def __init__(self, *, include=(2967, 3985), failed=()):
        self.include = include
        self.failed = failed
        self.calls = []

    async def call_tool(self, gateway, arguments):
        self.calls.append((gateway, arguments))
        leaf = arguments["tool"]
        if leaf == "hub_list_apps":
            assert gateway == "hub_read_apps_code"
            data = {"apps": [
                {"id": rid, "name": "Existing Rule " + str(rid),
                 "type": "Rule-5.1", "user": False, "parentId": 169}
                for rid in self.include
            ] + [
                {"id": 8500, "name": "Unrelated user app",
                 "type": "Custom", "user": True, "parentId": 169},
            ]}
        else:
            assert leaf == "hub_set_rule"
            assert gateway == "hub_manage_native_rules_and_apps"
            args = arguments["args"]
            assert args == {
                "operation": "read", "rule_id": args["rule_id"],
                "args": {"sections": ["triggers", "settings"]},
            }
            rid = args["rule_id"]
            # A wrong returned rule ID is not target verified.
            data = _document(9999 if rid in self.failed else rid)
        return MCPToolResult(name=gateway, arguments=arguments,
                             raw={}, text="", data=data, is_error=False)


def _run(*, question=REQUEST, include=(2967, 3985), failed=()):
    mcp = FakeMCP(include=include, failed=failed)
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        message, projection = asyncio.run(read_existing_dated_triggers(
            mcp, recorder, question=question,
            available_names=frozenset({
                "hub_read_apps_code", "hub_manage_native_rules_and_apps",
            }),
        ))
        receipts = recorder.receipts()
    finally:
        recorder.reset(token)
    return mcp, message, projection, receipts


def test_targeted_retry_source_scope_and_nonmutating_exact_ids():
    assert is_existing_dated_trigger_question(REQUEST)
    assert _requested_rule_ids(REQUEST) == ["2967", "3985"]
    mcp, msg, data, evidence = _run(failed=(2967,))
    assert data["scanMode"] == "targeted-rule-ids"
    assert data["requestedRuleIds"] == ["2967", "3985"]
    assert data["requestedRuleIdsNotVisible"] == []
    assert data["scanOffset"] is None
    assert data["scanLimit"] == 4
    assert data["eligibleVisibleNativeRules"] == 2
    assert data["inventoryPageTraversalComplete"] is True
    assert data["scannedRuleIds"] == [
        {"ruleId": "2967", "readVerified": False},
        {"ruleId": "3985", "readVerified": True},
    ]
    assert data["savedDatedFieldReadbackVerified"] is False
    assert data["absenceProven"] is False
    assert data["readinessForMutation"] is False
    assert len(mcp.calls) == 3  # 1 inventory + 2 native reads
    assert [a["args"]["rule_id"] for _, a in mcp.calls[1:]] == [2967, 3985]
    assert all(a["tool"] in ("hub_list_apps", "hub_set_rule")
               for _, a in mcp.calls)
    assert all(a["args"].get("operation", "read") == "read"
               for _, a in mcp.calls)
    assert all(e["mutates"] is False and e["effect"] == "read"
               for e in evidence)
    assert "Exact-ID retry: requested 2967, 3985" in msg
    assert "still lacking a complete typed read: 2967" in msg
    assert "Resume with scan offset" not in msg
    assert "no hub-wide absence conclusion" in msg

    original = AgentOutcome(message=msg, request_class="live-read",
                            choices=[], evidence=evidence)
    final = apply_shared_investigation_completion(original, REQUEST)
    assert final.message == msg
    assert final.investigation_coverage["domain"] == "native_dated_trigger_discovery"
    assert final.investigation_coverage["readinessForMutation"] is False
    assert final.investigation_coverage["questionResolved"] is False


def test_target_ids_must_be_returned_as_verified_native_child_rows():
    mcp, msg, data, _ = _run(include=(3985,))
    assert len(mcp.calls) == 2
    assert [a["args"]["rule_id"] for _, a in mcp.calls[1:]] == [3985]
    assert data["requestedRuleIdsNotVisible"] == ["2967"]
    assert "No direct read was attempted for those IDs" in msg
    assert data["absenceProven"] is False


def test_ids_cannot_be_inferred_from_dates_or_other_numbers():
    assert _requested_rule_ids(
        "Read-only inspect existing Rule Machine dated triggers on 2026-11-05, offset 36"
    ) == []
    assert _requested_rule_ids(
        "Retry read-only existing Rule Machine dated triggers for rule IDs "
        "2967, 3985, 4055, 4056 and 4057"
    ) == []
    assert _requested_rule_ids("Retry for rule IDs 0 and 3985") == []
    assert _requested_rule_ids("Retry for rule IDs 3985 and 3985") == []


def test_invalid_target_id_list_has_no_mcp_calls_or_unrelated_offset_scan():
    bad = (
        "Read-only retry of existing native Rule Machine dated triggers for "
        "rule IDs 2967, 3985, 4000, 4001 and 4002. No changes."
    )
    assert is_existing_dated_trigger_question(bad)
    mcp, msg, data, receipts = _run(question=bad)
    assert not mcp.calls
    assert data["scanMode"] == "invalid-target-rule-ids"
    assert data["scanLimit"] == 0
    assert data["scannedRuleIds"] == []
    assert data["readinessForMutation"] is False
    assert "No Hubitat inventory, native document or modifying calls" in msg
    assert len(receipts) == 1
    assert receipts[0]["mutates"] is False


def test_simple_offset_mode_does_not_change_for_existing_scans():
    question = ("Read-only inspect existing native Rule Machine dated triggers "
                "at scan offset 1 for atDate# settings.")
    mcp, msg, data, _ = _run(question=question, include=(2967, 3985))
    assert data["scanMode"] == "offset-batch"
    assert data["requestedRuleIds"] == []
    assert data["scanOffset"] == 1
    assert len(mcp.calls) == 2
    assert mcp.calls[1][1]["args"]["rule_id"] == 3985
    assert "Scan offset: 1" in msg
