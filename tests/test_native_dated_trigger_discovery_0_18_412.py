"""Read-only native dated-trigger discovery, source-bounded and no form opens."""
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
from native_dated_trigger_discovery import (
    is_existing_dated_trigger_question, project_existing_dated_fields,
    read_existing_dated_triggers, existing_dated_trigger_coverage,
)
from shared_investigation_completion import apply_shared_investigation_completion


REQUEST = (
    "Perform a read-only investigation of existing native Rule Machine dated triggers. "
    "Search for an already-existing Rule Machine rule using Certain Time (and optional date). "
    "If one exists, inspect saved native trigger settings time#, atTime#, date# and atDate# "
    "and whether the date is enabled. Use only safe read-only sources. "
    "Do not invoke form-opening operations that may execute app code. "
    "If no suitable existing rule exists, report the limitation. "
    "Do not create a test rule. Compare installed MCP v5.1.5; include Technical JSON."
)
CONTINUE = (
    "Read-only: continue scan of existing native Rule Machine dated triggers "
    "from offset 12; inspect atDate# saved state, no modifications."
)


def _doc(rule_id: int, *, date_value="2026-11-10", enabled=True, omit=()):
    entries = [
        ("time1", "enum", "A specific time"),
        ("atTime1", "time", "2026-11-10T15:35:00.000+0000"),
        ("date1", "bool", enabled),
        ("atDate1", "date", date_value),
        ("unrelatedPassword", "password", "PRIVATE_CREDENTIAL"),
    ]
    return {
        "rule_id": rule_id,
        "settings": [
            {"name": name, "type": kind, "value": value}
            for name, kind, value in entries if name not in omit
        ],
        "triggers": {"1": "Certain Time (and optional date)"},
    }


def _apps(n=15):
    return {
        "apps": [
            {"id": 4100 + i, "name": "Dated scan rule " + str(i),
             "type": "Rule-5.1", "user": False, "parentId": 169}
            for i in range(n)
        ] + [
            {"id": 9900, "name": "User app with date",
             "type": "Custom App", "user": True, "parentId": 300},
        ],
        "count": n + 1, "filter": "children",
        "totalOnHub": n + 25,
    }


class FakeMCP:
    def __init__(self, *, n=15, matching=4103, no_gateway=False,
                 doc_override=None):
        self.n = n
        self.matching = matching
        self.no_gateway = no_gateway
        self.doc_override = doc_override
        self.calls = []

    async def call_tool(self, gateway, args):
        self.calls.append((gateway, args))
        leaf = args["tool"]
        if leaf == "hub_list_apps":
            assert gateway == "hub_read_apps_code"
            assert args["args"]["scope"] == "instances"
            assert args["args"]["filter"] == "children"
            data = _apps(self.n)
        elif leaf == "hub_set_rule":
            assert gateway == "hub_manage_native_rules_and_apps"
            assert args["args"]["operation"] == "read"
            assert set(args["args"]["args"]["sections"]) == {"triggers", "settings"}
            rid = args["args"]["rule_id"]
            data = (
                self.doc_override if self.doc_override is not None
                else _doc(rid, enabled=(rid == self.matching))
            )
        else:
            raise AssertionError("Unexpected MCP operation " + leaf)
        return MCPToolResult(
            name=gateway, arguments=args, raw={}, text="",
            data=data, is_error=False,
        )


def _run(*, question=REQUEST, n=15, matching=4103,
         expose_reader=True, doc_override=None):
    mcp = FakeMCP(n=n, matching=matching, doc_override=doc_override)
    rec = EvidenceRecorder()
    token = rec.begin()
    try:
        answer, projection = asyncio.run(read_existing_dated_triggers(
            mcp, rec, question=question,
            available_names=frozenset(
                {"hub_read_apps_code", "hub_manage_native_rules_and_apps"}
                if expose_reader else {"hub_read_apps_code"}
            ),
        ))
        receipts = rec.receipts()
    finally:
        rec.reset(token)
    return mcp, answer, projection, receipts


def test_exact_failed_question_matches_specialist_and_no_test_rule_prohibition():
    assert is_existing_dated_trigger_question(REQUEST)
    assert is_existing_dated_trigger_question(CONTINUE)
    assert not is_existing_dated_trigger_question(
        "Create a new Rule Machine dated one-time rule on Tuesday."
    )
    assert not is_existing_dated_trigger_question(
        "Read-only native Rule Machine dated one-time rule creation preflight."
    )
    assert not is_existing_dated_trigger_question(
        "Read-only investigate why existing Light 2 went off."
    )


def test_exact_positive_readback_projected_fields_and_no_private_values():
    doc = _doc(4103)
    projection = project_existing_dated_fields(doc, "4103")
    assert projection["ruleId"] == "4103"
    assert projection["savedDatedFieldSetObserved"] is True
    assert len(projection["returnedDateFieldGroups"]) == 1
    group = projection["returnedDateFieldGroups"][0]
    assert group["nativeTriggerRowPresent"] is True
    assert group["dateEnabled"] is True
    assert group["fields"]["atDate"]["name"] == "atDate1"
    assert group["fields"]["atDate"]["type"] == "date"
    assert group["fields"]["atDate"]["value"] == "2026-11-10"
    assert "PRIVATE_CREDENTIAL" not in str(projection)
    assert "unrelatedPassword" not in str(projection)
    assert projection["runtimeExecutionVerified"] is False


def test_invalid_or_disabled_dated_state_not_verified():
    for change in (
        {"date_value": "2026-02-30"},
        {"enabled": False},
        {"omit": ("atDate1",)},
        {"omit": ("date1",)},
        {"omit": ("time1",)},
        {"omit": ("atTime1",)},
    ):
        doc = _doc(4103, **change)
        p = project_existing_dated_fields(doc, "4103")
        assert p is not None
        assert p["savedDatedFieldSetObserved"] is False
    doc = _doc(4103)
    doc["settings"] = [
        x if x["name"] != "atDate1"
        else dict(x, type="text")
        for x in doc["settings"]
    ]
    assert not project_existing_dated_fields(doc, "4103")[
        "savedDatedFieldSetObserved"
    ]


def test_id_mismatch_truncation_duplicate_fields_and_bad_shapes_fail_closed():
    doc = _doc(4103)
    assert project_existing_dated_fields(doc, "9999") is None
    assert project_existing_dated_fields(dict(doc, truncated=True), "4103") is None
    assert project_existing_dated_fields(dict(doc, nextCursor="1"), "4103") is None
    assert project_existing_dated_fields(dict(doc, settings="invalid"), "4103") is None
    doc["settings"].append(dict(doc["settings"][0]))
    assert project_existing_dated_fields(doc, "4103") is None


def test_actual_host_scan_reads_only_native_document_no_form_and_stops_at_match():
    mcp, answer, data, receipts = _run()
    assert data["savedDatedFieldReadbackVerified"] is True
    assert data["absenceProven"] is False
    assert data["scanOffset"] == 0
    assert len(data["scannedRuleIds"]) == 4
    assert data["verifiedDatedRules"][0]["ruleId"] == "4103"
    assert "atDate=2026-11-10" in answer
    assert "one-shot semantics are NOT established" in answer
    assert "40 child rules" not in answer
    assert "inactivity" not in answer.lower()
    assert all(
        args["tool"] in ("hub_list_apps", "hub_set_rule")
        for _, args in mcp.calls
    )
    assert all(
        args["args"].get("operation", "read") == "read"
        for _, args in mcp.calls
    )
    assert all(row.get("effect") == "read" and row.get("mutates") is False
               for row in receipts)
    assert receipts[-1]["evidence_kind"] == "typed_native_dated_trigger_discovery"

    outcome = AgentOutcome(
        message=answer, request_class="live-read",
        choices=[], evidence=receipts,
    )
    final = apply_shared_investigation_completion(outcome, REQUEST)
    assert final.message == answer
    assert final.investigation_coverage["domain"] == "native_dated_trigger_discovery"
    assert final.investigation_coverage["questionResolved"] is True
    assert final.investigation_coverage["readinessForMutation"] is False
    assert final.metrics["outcome"] == "success"


def test_bounded_no_match_stays_partial_and_continuation_has_forward_progress():
    mcp, answer, data, receipts = _run(matching=9999)
    assert data["savedDatedFieldReadbackVerified"] is False
    assert data["moreCandidatesMayExist"] is True
    assert len(data["scannedRuleIds"]) == 12
    assert len([1 for _, args in mcp.calls if args["tool"] == "hub_set_rule"]) == 12
    assert "Resume with scan offset 12" in answer
    assert "not evidence that none exist" in answer
    coverage = existing_dated_trigger_coverage(REQUEST, receipts)
    assert coverage["questionResolved"] is False
    assert coverage["domain"] == "native_dated_trigger_discovery"
    _, continued, more, _ = _run(question=CONTINUE, matching=9999)
    assert more["scanOffset"] == 12
    assert [r["ruleId"] for r in more["scannedRuleIds"]] == [
        "4112", "4113", "4114"
    ]
    assert "Resume with scan offset 15" not in continued


def test_missing_management_reader_keeps_partial_with_no_form_or_write():
    mcp, answer, data, receipts = _run(expose_reader=False)
    assert len(mcp.calls) == 1
    assert data["nativeReadGatewayAvailable"] is False
    assert data["savedDatedFieldReadbackVerified"] is False
    assert "no trigger state was inspected" in answer
    assert existing_dated_trigger_coverage(REQUEST, receipts)[
        "evidenceComplete"
    ] is False


def test_read_failure_or_wrong_rule_id_does_not_become_positive_evidence():
    _, answer, data, receipts = _run(
        n=1, doc_override=_doc(9999),
    )
    assert data["savedDatedFieldReadbackVerified"] is False
    assert data["scannedRuleIds"][0]["readVerified"] is False
    assert "No verified enabled dated-trigger field set" in answer
    assert receipts[1]["success"] is False
