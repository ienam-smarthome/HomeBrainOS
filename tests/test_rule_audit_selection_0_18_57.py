"""v0.18.57: prioritize source-confirmed Rule Machine rules and avoid AI timeout."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from rm_settings_dependency import is_rule_machine_app
from automation_dependency_probe import select_automation_probes, inspect_automation_dependencies
from composite_system_audit_policy import is_cross_domain_hub_audit_request
from automation_diagnostic_policy import is_broad_automation_runtime_diagnostic


def _inventory():
    items = [
        ("3892", "OwnTracks", "disabled", "app"),
        ("3951", "Power saving: Livingroom Nest Mini", "disabled", "rule"),
        ("513", "Room Lighting", "active", "app"),
        ("2317", "Bedroom 1 floor lamp", "active", "app"),
        ("3062", "Hallway dimmer", "active", "app"),
        ("3063", "Hallway dimmer button 1", "active", "app"),
        ("3931", "Big lamp scheduled OFF", "active", "rule"),
        ("3992", "Bedroom 3 lamp scheduled OFF", "active", "rule"),
    ]
    return {"inventory_identities": [
        {"id": ident, "name": name, "status": status, "type": kind}
        for ident, name, status, kind in items]}


def _scheduler():
    return {"status": "parsed", "candidateIdsByType": {"app": ["3892", "3951"]}}


def test_normalized_rule_is_priority_hint_not_version_proof():
    selected = select_automation_probes(_inventory(), _scheduler())
    assert [item["id"] for item in selected[:4]] == [
        "3892", "3951", "3931", "3992"]
    assert len(selected) == 6
    assert not is_rule_machine_app({"type": "rule", "name": "Big lamp"})
    assert is_rule_machine_app({"type": "Rule-5.1", "name": "Big lamp"})


class FakeMCP:
    def __init__(self, rm5=True):
        self.calls = []
        self.rm5 = rm5

    async def list_tools(self):
        return [SimpleNamespace(name="hub_read_apps_code")]

    async def call_tool(self, name, request):
        assert name == "hub_read_apps_code"
        self.calls.append(request)
        leaf = request["tool"]
        args = request["args"]
        if leaf == "hub_get_app_config":
            ident = str(args["appId"])
            app_type = ("Rule-5.1" if self.rm5 and ident in {"3931","3992","3951"}
                        else "app")
            return SimpleNamespace(is_error=False, data={
                "success": True, "app": {"id": int(ident), "type": app_type},
                "page": {"sections": [{"title": "Overview", "inputs": [], "paragraphs": []}]},
                **({"settings": {"onOffSwitch.3": {
                    ("7827" if ident == "3931" else "7841"): "private label"},
                    "tCapab33": "Periodic Schedule"}} if args["includeSettings"] else {})
            })
        assert leaf == "hub_list_device_dependents"
        assert set(args) == {"deviceId"}
        referenced = "3931" if str(args["deviceId"]) == "7827" else "3992"
        return SimpleNamespace(is_error=False, data={
            "success": True, "appsUsing": [{"id": referenced}]
        })


@pytest.mark.asyncio
async def test_live_shape_selects_both_rm_lighting_rules_for_indexed_settings():
    mcp = FakeMCP()
    report, receipts = await inspect_automation_dependencies(
        mcp, _inventory(), _scheduler())
    rm_settings = [row["args"]["appId"] for row in mcp.calls
                   if row["tool"] == "hub_get_app_config"
                   and row["args"]["includeSettings"] is True]
    assert rm_settings == ["3931", "3992"]
    dependent_reads = [row for row in mcp.calls
                       if row["tool"] == "hub_list_device_dependents"]
    assert {row["args"]["deviceId"] for row in dependent_reads} == {"7827", "7841"}
    assert report["summary"]["rmReferencesObserved"] == 2
    assert report["summary"]["typedActionDeviceOverlaps"] == []
    assert len(report["deviceDependentEdges"]) == 2
    assert len([e for e in receipts if
                e["evidence_kind"] == "chat_audit_rm_settings_shape"]) == 2
    assert "private label" not in str(report)
    assert "Periodic Schedule" not in str(receipts)


@pytest.mark.asyncio
async def test_normalized_rule_without_explicit_rm5_config_type_not_interpreted():
    mcp = FakeMCP(rm5=False)
    report, receipts = await inspect_automation_dependencies(
        mcp, _inventory(), _scheduler())
    assert not [row for row in mcp.calls
                if row["tool"] == "hub_get_app_config"
                and row["args"]["includeSettings"] is True]
    assert not [row for row in mcp.calls
                if row["tool"] == "hub_list_device_dependents"]
    assert report["summary"]["rmReferencesObserved"] == 0
    assert not [row for row in receipts if
                row["evidence_kind"] == "chat_audit_rm_settings_shape"]


def test_full_hub_automation_audit_does_not_auto_opt_into_ai(monkeypatch):
    import app as application

    question = (
        "Perform a comprehensive read-only audit of my entire Hubitat hub. "
        "Investigate all my automations, scheduled jobs, device targets "
        "and dependencies. Do not change anything."
    )
    assert is_cross_domain_hub_audit_request(question)
    assert is_broad_automation_runtime_diagnostic(question)

    invoked = []

    async def full_audit(_audit, _mcp, **kwargs):
        invoked.append(kwargs)
        return SimpleNamespace(message="Host-assembled audit",
                               route="comprehensive-system-audit")

    async def reject_model(*_args, **_kwargs):
        raise AssertionError("Unexpected general agent call")

    monkeypatch.setattr(application, "run_comprehensive_chat_audit", full_audit)
    monkeypatch.setattr(application.agent, "process_user_request_result", reject_model)
    monkeypatch.setitem(application.OPTIONS, "automation_diagnostic_ai_analysis_enabled", True)
    monkeypatch.setitem(application.OPTIONS, "comprehensive_audit_ai_analysis_enabled", False)

    response = asyncio.run(application._agent_request(
        application.ChatRequest(prompt=question, model_tier="free")
    ))
    assert response.message == "Host-assembled audit"
    assert invoked == [{}]


def test_explicit_comprehensive_ai_opt_in_still_supported(monkeypatch):
    import app as application

    prompt = (
        "Audit my entire Hubitat hub: review all my automations, "
        "scheduled jobs and device dependencies."
    )
    assert is_cross_domain_hub_audit_request(prompt)
    invoked = []

    async def full_audit(_audit, _mcp, **kwargs):
        invoked.append(kwargs)
        return SimpleNamespace(message="Host audit", route="comprehensive-system-audit")

    monkeypatch.setattr(application, "run_comprehensive_chat_audit", full_audit)
    monkeypatch.setitem(application.OPTIONS, "comprehensive_audit_ai_analysis_enabled", True)
    monkeypatch.setitem(application.OPTIONS, "automation_diagnostic_ai_analysis_enabled", False)

    asyncio.run(application._agent_request(application.ChatRequest(prompt=prompt)))
    assert len(invoked) == 1
    assert callable(invoked[0].get("analysis_chat"))
