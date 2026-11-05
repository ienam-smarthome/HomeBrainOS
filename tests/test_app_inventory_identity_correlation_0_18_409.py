"""Typed, bounded Hubitat app inventory/class correlation regression tests."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from app_identity_inventory_evidence import (
    project_app_inventory_page, match_app_inventory_receipts,
)
from app_class_identity_receipt import reconcile_app_class_identity_answer
from investigation_intelligence import assess_investigation, plan_investigation
from evidence_recorder import EvidenceRecorder
from mcp_client import MCPToolResult
from tool_executor import ToolExecutor
from mcp_agent_orchestrator import AgentOutcome
from observed_agent_outcome import build_observed_agent_outcome
from shared_investigation_completion import apply_shared_investigation_completion


def _call(scope):
    return {
        "tool": "hub_list_apps",
        "args": {"scope": scope, "nameFilter": "Rule Machine"},
    }


def _instance():
    return {
        "apps": [
            {"id": 169, "name": "Rule Machine", "type": "Rule Machine",
             "appTypeId": 18, "user": False, "parentId": None},
            {"id": 186, "name": "Rule Machine Test", "type": "Rule Machine",
             "appTypeId": 200, "user": True, "parentId": 169},
            {"id": 205, "name": "Some Other App", "appTypeId": 18,
             "user": False, "parentId": None},
        ],
        "count": 3, "filter": "all", "totalOnHub": 100,
    }


def _types():
    return {
        "apps": [
            {"id": 18, "name": "Rule Machine", "namespace": "hubitat",
             "system": True, "isBuiltIn": True},
            {"id": 200, "name": "Rule Machine", "namespace": "community",
             "system": False, "isBuiltIn": False},
        ],
        "count": 2, "source": "hub_api",
    }


def _receipt(scope, data):
    args = _call(scope)
    details = project_app_inventory_page("hub_read_apps_code", args, data)
    assert details is not None
    return {
        "tool": "hub_read_apps_code", "sub_tool": "hub_list_apps",
        "success": True, "effect": "read", "mutates": False,
        "evidence_kind": (
            "typed_app_inventory_page" if scope == "instances"
            else "typed_app_type_catalog_page"
        ),
        "arguments": args, "details": details,
    }


def test_exact_instance_row_and_source_catalog_type_are_projected_safely():
    inst = _receipt("instances", _instance())["details"]
    assert inst["inventoryScope"] == "instances"
    assert inst["rows"][0] == {
        "appId": "169", "reportedName": "Rule Machine",
        "appTypeId": "18", "reportedType": "Rule Machine",
        "reportedUser": False, "parentIdPresent": True,
        "reportedParentId": None,
    }
    assert len(inst["rows"]) == 2  # unfiltered unrelated app omitted
    assert inst["nativeClassBindingVerified"] is False
    types = _receipt("types", _types())["details"]
    assert types["rows"][0] == {
        "typeId": "18", "reportedTypeName": "Rule Machine",
        "reportedNamespace": "hubitat",
        "reportedSystem": True, "reportedIsBuiltIn": True,
    }
    assert types["catalogSource"] == "hub_api"


def test_exact_id_join_not_ambiguous_name_join():
    receipts = [_receipt("instances", _instance()), _receipt("types", _types())]
    answer = match_app_inventory_receipts(receipts, "169")
    assert answer["instanceTypeId"] == "18"
    assert answer["typeIdJoinObserved"] is True
    assert len(answer["matchedTypeRows"]) == 1
    assert answer["matchedTypeRows"][0]["reportedNamespace"] == "hubitat"
    assert answer["nativeClassBindingVerified"] is False
    message, changed = reconcile_app_class_identity_answer(
        "App 169 is native and confirmed.", receipts, {"requirements": []},
        "Read app instance 169 Rule Machine native parent",
    )
    assert changed
    assert "appTypeId=18" in message
    assert "type-catalog id=18" in message
    assert "isBuiltIn=true" in message
    assert "namespace 'hubitat'" in message
    assert "type-catalog id=200" not in message
    assert "Native class/parent verification: unresolved" in message


def test_absent_or_malformed_type_id_stays_unverified():
    inst = _instance()
    del inst["apps"][0]["appTypeId"]
    match = match_app_inventory_receipts(
        [_receipt("instances", inst), _receipt("types", _types())], "169",
    )
    assert match["instanceTypeId"] is None
    assert match["typeIdJoinObserved"] is False
    inst["apps"][0]["appTypeId"] = True
    assert match_app_inventory_receipts([_receipt("instances", inst)], "169")[
        "instanceTypeId"
    ] is None


def test_wrong_source_and_tampered_scope_are_never_type_proof():
    assert project_app_inventory_page(
        "hub_read_apps_code", _call("types"),
        dict(_types(), source="mcp_only"),
    ) is None
    assert project_app_inventory_page(
        "hub_read_apps_code",
        {"tool": "hub_list_apps", "args": {"scope": "instances"}},
        _instance(),
    ) is None
    good = _receipt("instances", _instance())
    good["arguments"]["args"]["nameFilter"] = "Unrelated"
    assert match_app_inventory_receipts([good], "169") is None
    good = _receipt("instances", _instance())
    good["mutates"] = True
    assert match_app_inventory_receipts([good], "169") is None


def test_partial_filtered_pages_never_claim_missing_type_is_absent():
    inst = _receipt("instances", _instance())
    types = _types()
    types["apps"] = [types["apps"][1]]
    catalog = _receipt("types", types)
    match = match_app_inventory_receipts([inst, catalog], "169")
    assert match["instanceTypeId"] == "18"
    assert match["typeIdJoinObserved"] is False
    message, _ = reconcile_app_class_identity_answer(
        "Native type is missing.", [inst, catalog], {"requirements": []},
        "Check app 169 native type",
    )
    assert "Partial reads do not establish that the type is absent" in message


def test_conflicting_instance_type_ids_do_not_verify_join():
    a = _receipt("instances", _instance())
    b = _receipt("instances", _instance())
    b["details"]["rows"][0]["appTypeId"] = "200"
    match = match_app_inventory_receipts([a, b, _receipt("types", _types())], "169")
    assert match["instanceTypeIdConflict"] is True
    assert match["instanceTypeId"] is None
    assert not match["typeIdJoinObserved"]


def test_unsafe_names_and_unfiltered_broad_results_do_not_leak():
    inst = _instance()
    inst["apps"].append({
        "id": 211, "name": "Rule Machine token secret",
        "appTypeId": 44, "privateSettings": "credential",
    })
    text = str(_receipt("instances", inst)["details"])
    assert "credential" not in text
    assert "token secret" not in text
    assert "Some Other App" not in text
    assert project_app_inventory_page(
        "hub_read_apps_code",
        {"tool": "hub_list_apps", "args": {"scope": "instances"}},
        inst,
    ) is None


def test_actual_executor_emits_two_typed_receipts():
    class FakeMCP:
        async def call_tool(self, gateway, args):
            data = _instance() if args["args"]["scope"] == "instances" else _types()
            return MCPToolResult(
                name=gateway, arguments=args, raw={},
                text="", data=data, is_error=False,
            )
    recorder = EvidenceRecorder()
    token = recorder.begin()
    try:
        executor = ToolExecutor(FakeMCP(), recorder)
        asyncio.run(executor.execute("hub_read_apps_code", _call("instances")))
        asyncio.run(executor.execute("hub_read_apps_code", _call("types")))
        receipts = recorder.receipts()
    finally:
        recorder.reset(token)
    assert [r["evidence_kind"] for r in receipts] == [
        "typed_app_inventory_page", "typed_app_type_catalog_page",
    ]
    assert match_app_inventory_receipts(receipts, "169")["typeIdJoinObserved"] is True


def test_shared_completion_marks_instance_type_observed_but_native_unverified():
    receipts = [_receipt("instances", _instance()), _receipt("types", _types())]
    request = (
        "Investigate whether Rule Machine app instance 169 is independently "
        "verified as a native class. Do not change rules."
    )
    agent = AgentOutcome(
        message="This looks like the native Rule Machine parent.",
        request_class="live-read", choices=[], evidence=receipts,
    )
    observed = build_observed_agent_outcome(
        agent, {"outcome": "success", "counters": {}, "timings_ms": {}},
    )
    final = apply_shared_investigation_completion(observed, request)
    coverage = final.investigation_coverage
    assert coverage["domain"] == "app_class_identity"
    assert coverage["appIdentityCorrelation"]["sourceTypeId"] == "18"
    assert coverage["appIdentityCorrelation"]["typeIdJoinObserved"] is True
    assert coverage["appIdentityCorrelation"]["nativeClassBindingVerified"] is False
    states = {r["key"]: r["state"] for r in coverage["requirements"]}
    assert states["instance_identity"] == "observed"
    assert states["native_class_binding"] == "checked-unverified"
    assert coverage["evidenceComplete"] is False
    assert "isBuiltIn=true" in final.message
    assert "Native class/parent verification: unresolved" in final.message
