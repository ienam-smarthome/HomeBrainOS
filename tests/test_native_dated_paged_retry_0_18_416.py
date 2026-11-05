"""v0.18.416: safe bounded native date-field pagination and failure diagnosis."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from mcp_client import MCPToolResult, MCPTool
from evidence_recorder import EvidenceRecorder
from tool_registry import ToolEffect, classify_tool_effect
from native_dated_paged_reader import (
    read_paged_native_dated_document, read_failure_category,
)
from native_dated_trigger_discovery import read_existing_dated_triggers

PROMPT = (
    "Retry read-only inspection of existing native Rule Machine dated triggers "
    "for rule IDs 2967 and 3985. Check saved time#, atTime#, date# and atDate# "
    "field types and values. Keep rule-writing authorisation disabled. "
    "No form openings or modifications. Include Technical JSON."
)
_REVISION = "b" * 64
_SENSITIVE = "SECRET_PASSWORD_DO_NOT_ECHO"


def _result(gateway, args, data, *, error=False):
    return MCPToolResult(
        name=gateway, arguments=args, raw={},
        text=str(data.get("error") or "") if isinstance(data, dict) else "",
        data=data, is_error=error,
    )


def _settings():
    rows = [
        {"name": f"nonRelevant{i}", "type": "password" if i == 5 else "string",
         "value": _SENSITIVE if i == 5 else "unused"}
        for i in range(57)
    ]
    rows += [
        {"name": "time1", "type": "enum", "value": "A specific time"},
        {"name": "atTime1", "type": "time", "value": "15:35"},
        {"name": "date1", "type": "bool", "value": True},
        {"name": "atDate1", "type": "date", "value": "2026-11-10"},
    ]
    return sorted(rows, key=lambda x: x["name"])


class PagedServer:
    def __init__(self, *, fail_mode="unpaged-too-large", fault=None, native_ids=(2967, 3985)):
        self.calls = []
        self.fail_mode = fail_mode
        self.fault = fault
        self.native_ids = native_ids

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        leaf = args["tool"]
        if leaf == "hub_list_apps":
            return _result(gateway, args, {"apps": [
                {"id": i, "name": f"Rule {i}", "type": "Rule-5.1",
                 "parentId": 169, "user": False}
                for i in self.native_ids
            ]})
        assert leaf == "hub_set_rule"
        assert gateway == "hub_manage_native_rules_and_apps"
        body = args["args"]
        assert body["operation"] == "read"
        assert body["rule_id"] in self.native_ids
        options = body["args"]
        assert classify_tool_effect(MCPTool(gateway, gateway, {}), args) is ToolEffect.READ
        if options["sections"] == ["triggers", "settings"]:
            if self.fail_mode == "mismatch":
                return _result(gateway, args, {"rule_id": 9999, "settings": [], "triggers": {}})
            if self.fail_mode == "valid":
                return _result(gateway, args, {
                    "rule_id": body["rule_id"],
                    "settings": _settings(), "triggers": {"1": "Certain Time"},
                })
            return _result(gateway, args, {
                "success": False,
                "error": "response exceeds size limit " + _SENSITIVE,
            }, error=True)
        assert options["sections"] in (["triggers"], ["settings"])
        assert type(options["limit"]) is int and options["limit"] <= 50
        section = options["sections"][0]
        offset = int(options["cursor"] or 0)
        all_rows = _settings() if section == "settings" else {"1": "Certain Time"}
        entries = (
            all_rows[offset:offset + 50] if isinstance(all_rows, list)
            else dict(list(all_rows.items())[offset:offset + 50])
        )
        next_cursor = (
            str(offset + len(entries))
            if offset + len(entries) < len(all_rows) else None
        )
        revision = _REVISION
        total = len(all_rows)
        if self.fault == "revision" and section == "settings" and offset > 0:
            revision = "c" * 64
        elif self.fault == "too-many-rows" and section == "settings":
            total = 10000
        elif self.fault == "wrong-id":
            return _result(gateway, args, {
                "rule_id": 9999,
                "page": {"offset": offset, "limit": 50,
                         "revision": revision, "total": total},
                section: entries, "nextCursor": next_cursor,
            })
        elif self.fault == "cursor-loop" and section == "settings" and next_cursor:
            next_cursor = str(offset)
        data = {
            "rule_id": body["rule_id"],
            "page": {"offset": offset, "limit": 50,
                     "revision": revision, "total": total},
            section: entries, "nextCursor": next_cursor,
        }
        return _result(gateway, args, data)


def _run(server, *, question=PROMPT):
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        answer, details = asyncio.run(read_existing_dated_triggers(
            server, recorder, question=question,
            available_names=frozenset({
                "hub_read_apps_code", "hub_manage_native_rules_and_apps",
            }),
        ))
        evidence = recorder.receipts()
    finally:
        recorder.reset(token)
    return answer, details, evidence


def test_source_error_is_categorized_without_leaking_native_response():
    server = PagedServer()
    reply = asyncio.run(server.call_tool(
        "hub_manage_native_rules_and_apps",
        {"tool": "hub_set_rule", "args": {
            "operation": "read", "rule_id": 2967,
            "args": {"sections": ["triggers", "settings"]},
        }},
    ))
    assert read_failure_category(reply, "2967") == "response_size_limit"


def test_exact_two_id_retry_falls_back_to_paged_source_and_finishes_both():
    server = PagedServer()
    answer, details, evidence = _run(server)
    assert details["scanMode"] == "targeted-rule-ids"
    assert details["requestedRuleIds"] == ["2967", "3985"]
    assert details["scannedRuleIds"] == [
        {"ruleId": "2967", "readVerified": True},
        {"ruleId": "3985", "readVerified": True},
    ]
    assert details["savedDatedFieldReadbackVerified"] is True
    assert len(details["verifiedDatedRules"]) == 2
    for detail in details["readDiagnostics"]:
        assert detail["unpagedFailureCode"] == "response_size_limit"
        assert detail["pagedAttempted"] is True
        assert detail["pagedOutcome"] == "complete"
        assert detail["pagedSectionsRead"] == {"triggers": 1, "settings": 2}
    # inventory + two * (one unpaged + one trigger page + two settings pages)
    assert len(server.calls) == 9
    assert all(
        args["tool"] in ("hub_list_apps", "hub_set_rule")
        and args["args"].get("operation", "read") == "read"
        for _, args in server.calls
    )
    assert all(r["effect"] == "read" and r["mutates"] is False for r in evidence)
    assert len([r for r in evidence if r["tool"] == "homebrain_native_dated_paged_projection"]) == 2
    assert "Stored dated fields found" in answer
    assert _SENSITIVE not in str(details)
    assert _SENSITIVE not in str(evidence)
    assert _SENSITIVE not in answer
    assert details["readinessForMutation"] is False
    assert details["absenceProven"] is False


@pytest.mark.parametrize("fault,reason", [
    ("revision", "changed_page_revision"),
    ("too-many-rows", "unbounded_or_changed_page"),
    ("wrong-id", "rule_id_mismatch"),
    ("cursor-loop", "invalid_page_cursor"),
])
def test_bad_paged_response_fails_closed_and_reports_only_safe_reason(fault, reason):
    server = PagedServer(fault=fault, native_ids=(2967,))
    answer, details, evidence = _run(server, question=PROMPT)
    assert details["requestedRuleIdsNotVisible"] == ["3985"]
    assert details["scannedRuleIds"] == [{"ruleId": "2967", "readVerified": False}]
    assert details["readDiagnostics"][0]["pagedOutcome"] == reason
    assert details["savedDatedFieldReadbackVerified"] is False
    assert "Requested rule IDs still lacking a complete typed read: 2967" in answer
    assert _SENSITIVE not in str(details)
    assert _SENSITIVE not in str(evidence)
    assert details["readinessForMutation"] is False


def test_wrong_unpaged_rule_identity_is_not_paged_or_reclassified_as_valid():
    server = PagedServer(fail_mode="mismatch", native_ids=(2967,))
    _, details, evidence = _run(server, question=PROMPT)
    assert len(server.calls) == 2
    assert details["scannedRuleIds"] == [{"ruleId": "2967", "readVerified": False}]
    assert details["readDiagnostics"][0]["unpagedFailureCode"] == "rule_id_mismatch"
    assert details["readDiagnostics"][0]["pagedAttempted"] is False
    assert all(r["mutates"] is False for r in evidence)


def test_successful_original_read_does_not_add_paged_calls():
    server = PagedServer(fail_mode="valid", native_ids=(2967,))
    _, details, evidence = _run(server, question=PROMPT)
    assert len(server.calls) == 2
    assert details["scannedRuleIds"] == [{"ruleId": "2967", "readVerified": True}]
    assert details["readDiagnostics"][0]["pagedAttempted"] is False
    assert len([r for r in evidence if r["evidence_kind"] == "typed_native_dated_trigger_page"]) == 0


def test_ordinary_offset_scan_does_not_retry_failed_reads():
    server = PagedServer(native_ids=(2967,))
    question = (
        "Read-only inspect existing native Rule Machine dated triggers "
        "at scan offset 0 for atDate# settings. Never modify."
    )
    _, details, _ = _run(server, question=question)
    assert len(server.calls) == 2
    assert details["scanMode"] == "offset-batch"
    assert details["readDiagnostics"][0]["pagedAttempted"] is False
    assert details["scannedRuleIds"] == [{"ruleId": "2967", "readVerified": False}]
