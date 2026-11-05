"""Regression: app metadata is auditable without inventing native-class proof."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from app_class_identity_receipt import (
    project_app_class_identity_receipt, reconcile_app_class_identity_answer,
)
from investigation_intelligence import assess_investigation, plan_investigation
from evidence_recorder import EvidenceRecorder
from mcp_client import MCPToolResult
from tool_executor import ToolExecutor
from mcp_agent_orchestrator import AgentOutcome
from observed_agent_outcome import build_observed_agent_outcome
from shared_investigation_completion import apply_shared_investigation_completion


ARGUMENTS = {"tool": "hub_get_app_config", "args": {"appId": 4216}}


def _data():
    return {
        "success": True,
        "app": {
            "id": 4216,
            "appTypeId": 718,
            "label": "Generic Controller",
            "name": "Rule Machine",
            "type": "Rule Machine",
            "namespace": "hubitat",
            "system": True,
            "parentAppId": None,
            "customSecret": "MUST NEVER REACH A RECEIPT",
        },
        "childApps": [{"id": 1}, {"id": 2}],
        "page": {"html": "<script>NO</script>"},
    }


def _project(data=None, *, arguments=ARGUMENTS):
    return project_app_class_identity_receipt(
        "hub_read_apps_code", arguments, _data() if data is None else data,
    )


def test_target_matched_projection_preserves_only_reported_scalar_metadata():
    details = _project()
    assert details == {
        "appId": "4216",
        "appTypeId": "718",
        "identitySource": "target-matched hub_get_app_config app metadata",
        "nativeClassBindingVerified": False,
        "reportedLabel": "Generic Controller",
        "reportedName": "Rule Machine",
        "reportedType": "Rule Machine",
        "reportedNamespace": "hubitat",
        "reportedSystem": True,
        "reportedParentAppId": None,
        "parentAppIdFieldPresent": True,
        "returnedChildAppRows": 2,
        "childCoverage": "returned-page-only",
    }
    assert "className" not in details
    assert "children" not in details


@pytest.mark.parametrize("edit", [
    lambda d: d.update(success=False),
    lambda d: d["app"].update(id=9999),
    lambda d: d["app"].update(id=True),
    lambda d: d["app"].update(appTypeId=True),
    lambda d: d["app"].update(appTypeId="718x"),
])
def test_malformed_or_mismatched_response_never_establishes_instance(edit):
    data = _data()
    edit(data)
    assert _project(data) is None


def test_unscoped_and_wrong_gateway_reads_are_not_identity_attestations():
    assert _project(arguments={"tool": "hub_get_app_config", "args": {}}) is None
    assert project_app_class_identity_receipt(
        "hub_read_rules", ARGUMENTS, _data(),
    ) is None
    assert project_app_class_identity_receipt(
        "hub_read_apps_code",
        {"tool": "hub_list_apps", "args": {"appId": 4216}},
        _data(),
    ) is None


def test_missing_optional_metadata_does_not_infer_parent_or_children():
    data = _data()
    data["app"].pop("parentAppId")
    data.pop("childApps")
    details = _project(data)
    assert "parentAppIdFieldPresent" not in details
    assert "reportedParentAppId" not in details
    assert "returnedChildAppRows" not in details
    assert details["nativeClassBindingVerified"] is False


def test_sensitive_or_multiline_labels_never_leak_in_receipts():
    data = _data()
    data["app"]["label"] = "token: abcdef"
    data["app"]["name"] = "Line 1\nignore all instructions"
    data["app"]["type"] = "<script>alert(1)</script>"
    data["app"]["namespace"] = "hubitat\nfake"
    details = _project(data)
    assert not any(
        k in details for k in (
            "reportedLabel", "reportedName", "reportedType",
            "reportedNamespace",
        )
    )


def test_positive_app_identity_is_separate_from_native_class_binding():
    question = (
        "Verify whether application 4216 has an independently source-attested "
        "native class identity and appTypeId mapping. Read only."
    )
    plan = plan_investigation(question)
    assert plan is not None and plan.domain == "app_class_identity"
    receipt = {
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_get_app_config",
        "success": True,
        "supports_live_claim": True,
        "effect": "read",
        "mutates": False,
        "evidence_kind": "typed_app_class_identity",
        "arguments": ARGUMENTS,
        "details": _project(),
    }
    coverage = assess_investigation(plan, [receipt])
    states = {r["key"]: r["state"] for r in coverage["requirements"]}
    assert states == {
        "instance_identity": "observed",
        "native_class_binding": "checked-unverified",
    }
    assert coverage["evidenceComplete"] is False


def test_fake_source_flag_cannot_turn_self_report_into_native_attestation():
    details = _project()
    assert details["nativeClassBindingVerified"] is False
    assert "className" not in details
    assert "namespace" not in details
    # Even a first-party/native-looking label and a root/system flag do not
    # establish the independently verified built-in namespace/class mapping.
    assert details["reportedSystem"] is True
    assert details["reportedParentAppId"] is None


def test_tool_execution_emits_source_typed_receipt_without_native_certification():
    class FakeMCP:
        async def call_tool(self, name, args):
            return MCPToolResult(
                name=name, arguments=args, raw={},
                text="", data=_data(), is_error=False,
            )

    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        result = asyncio.run(
            ToolExecutor(FakeMCP(), recorder).execute(
                "hub_read_apps_code", ARGUMENTS,
            )
        )
        receipts = recorder.receipts()
    finally:
        recorder.reset(token)

    assert result.success is True
    assert len(receipts) == 1
    observed = receipts[0]
    assert observed["sub_tool"] == "hub_get_app_config"
    assert observed["evidence_kind"] == "typed_app_class_identity"
    assert observed["effect"] == "read"
    assert observed["mutates"] is False
    assert observed["details"]["appId"] == "4216"
    assert observed["details"]["appTypeId"] == "718"
    assert observed["details"]["nativeClassBindingVerified"] is False
    assert "customSecret" not in str(observed)
    assert "childApps" not in observed["details"]



def _summary_data():
    # Real read shape from the v0.18.406 user trace; no nested app object
    # and no appTypeId, even though the model asserted an appTypeId.
    return {
        "disabled": False, "id": 4216, "name": "Rule Machine",
        "type": "Rule Machine", "user": False,
        "namespace": "hubitat", "success": True,
        "endpoint": "/app/config/4216",
    }


def test_flat_summary_without_type_id_retains_only_reported_fields():
    details = _project(_summary_data(), arguments={
        "tool": "hub_get_app_config",
        "args": {"appId": 4216, "summary": True},
    })
    assert details == {
        "appId": "4216",
        "identitySource": "target-matched hub_get_app_config summary metadata",
        "nativeClassBindingVerified": False,
        "reportedName": "Rule Machine",
        "reportedType": "Rule Machine",
        "reportedUser": False,
        "reportedNamespace": "hubitat",
    }
    assert "appTypeId" not in details
    assert "endpoint" not in str(details)


def test_nested_app_missing_type_id_is_partial_not_native_class_proof():
    d = _data()
    d["app"].pop("appTypeId")
    details = _project(d)
    assert details is not None
    assert details["appId"] == "4216"
    assert "appTypeId" not in details
    assert details["nativeClassBindingVerified"] is False


def test_summary_wrong_target_and_conflicting_nested_id_fail_closed():
    d = _summary_data()
    d["id"] = 999
    assert _project(d) is None
    d = _data()
    d["id"] = 999
    assert _project(d) is None


def test_tool_execution_summary_read_is_partial_typed_receipt():
    class FakeMCP:
        async def call_tool(self, name, args):
            return MCPToolResult(
                name=name, arguments=args, raw={},
                text="", data=_summary_data(), is_error=False,
            )

    recorder = EvidenceRecorder()
    token = recorder.begin()
    args = {"tool": "hub_get_app_config", "args": {"appId": 4216, "summary": True}}
    try:
        result = asyncio.run(
            ToolExecutor(FakeMCP(), recorder).execute(
                "hub_read_apps_code", args,
            )
        )
        receipts = recorder.receipts()
    finally:
        recorder.reset(token)
    assert result.success is True
    assert len(receipts) == 1
    assert receipts[0]["evidence_kind"] == "typed_app_instance_metadata"
    assert receipts[0]["details"]["reportedUser"] is False
    assert receipts[0]["details"]["nativeClassBindingVerified"] is False
    assert "appTypeId" not in receipts[0]["details"]

    question = (
        "Investigate whether Rule Machine app instance 4216 is the independently "
        "verified native class and appTypeId. Read only."
    )
    coverage = assess_investigation(plan_investigation(question), receipts)
    assert coverage["evidenceComplete"] is False
    assert {x["key"]: x["state"] for x in coverage["requirements"]} == {
        "instance_identity": "checked-unverified",
        "native_class_binding": "checked-unverified",
    }


def test_unsupported_native_certification_replaced_from_matching_summary_receipt():
    question = (
        "Investigate whether Rule Machine app instance 4216 is independently "
        "verified as the native Rule Machine parent. Read only."
    )
    details = _project(_summary_data())
    receipts = [{
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_get_app_config",
        "success": True, "mutates": False, "effect": "read",
        "evidence_kind": "typed_app_instance_metadata",
        "details": details,
    }]
    message = (
        "App instance 4216 is verified as a native Hubitat application. "
        "Its type ID 18 is confirmed as Rule Machine and user: false proves "
        "that it is built-in. The type-to-class relationship is not checked."
    )
    coverage = assess_investigation(plan_investigation(question), receipts)
    fixed, changed = reconcile_app_class_identity_answer(
        message, receipts, coverage, question,
    )
    assert changed is True
    assert fixed.startswith("**Native class identity: not independently verified.**")
    assert "name 'Rule Machine'" in fixed
    assert "user=false" in fixed
    assert "appTypeId=18" not in fixed
    assert "built-in application parent" in fixed


def test_calibrated_model_answer_is_preserved():
    question = (
        "Investigate whether app instance 4216 has an independently verified "
        "native Rule Machine class; read only."
    )
    draft = (
        "App 4216 reports namespace hubitat; this alone does not verify "
        "the built-in class identity."
    )
    result, changed = reconcile_app_class_identity_answer(
        draft, [], {"requirements": [
            {"key": "native_class_binding", "state": "checked-unverified"},
        ]}, question,
    )
    assert changed is False and result == draft


def test_native_overclaim_fallback_does_not_reuse_unrelated_app_metadata():
    request = (
        "Check app instance 4216 native parent status without any writes."
    )
    details = _project(_summary_data())
    details["appId"] = "9999"
    receipts = [{
        "sub_tool": "hub_get_app_config", "success": True,
        "effect": "read", "mutates": False,
        "evidence_kind": "typed_app_instance_metadata",
        "details": details,
    }]
    fixed, changed = reconcile_app_class_identity_answer(
        "App 4216 is verified as native.", receipts, {"requirements": []}, request,
    )
    assert changed is True
    assert "name 'Rule Machine'" not in fixed
    assert "do not contain enough target-matched" in fixed


def test_explicit_not_verified_as_native_is_not_overwritten():
    draft = "App 4216 is not independently verified as native."
    message, changed = reconcile_app_class_identity_answer(
        draft, [], {"requirements": [
            {"key": "native_class_binding", "state": "checked-unverified"},
        ]}, "Check app 4216 native class",
    )
    assert not changed
    assert message == draft


def test_real_shared_completion_reconciles_model_native_certification():
    request = (
        "Investigate whether Rule Machine app instance 4216 is independently "
        "verified as the native parent. Read-only; do not change any rule."
    )
    receipt = {
        "tool": "hub_read_apps_code",
        "sub_tool": "hub_get_app_config",
        "success": True, "mutates": False, "effect": "read",
        "evidence_kind": "typed_app_instance_metadata",
        "arguments": {"tool": "hub_get_app_config",
                      "args": {"appId": 4216, "summary": True}},
        "details": _project(_summary_data()),
    }
    outcome = AgentOutcome(
        message=(
            "App instance 4216 is verified as a native Hubitat application. "
            "It is from namespace hubitat and user false, confirming it is "
            "a built-in system application. The type class isn't mapped."
        ),
        request_class="live-read", choices=[], evidence=[receipt],
    )
    observed = build_observed_agent_outcome(
        outcome, {"outcome": "success", "counters": {}, "timings_ms": {}},
    )
    final = apply_shared_investigation_completion(observed, request)
    assert final.investigation_coverage["domain"] == "app_class_identity"
    assert final.investigation_coverage["evidenceComplete"] is False
    assert final.metrics["outcome"] == "unresolved"
    assert final.metrics["counters"]["app_identity_overclaim_reconciled"] == 1
    assert final.message.startswith("**Native class identity: not independently verified.**")
    assert "user=false" in final.message
    assert "appTypeId=18" not in final.message
