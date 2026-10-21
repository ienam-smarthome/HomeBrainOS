"""RM 5.x current configuration references are not historical actions.

No raw settings/labels are published; broad scans stay bounded.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from rm_settings_dependency import interpret_rm_settings, is_rule_machine_app
from automation_dependency_probe import (
    select_automation_probes, inspect_automation_dependencies, analyse_dependency_probes,
    render_dependency_findings,
)


def rm_payload(ident="3992", device="7841", *, secrets=True):
    # Format comes from a 0.18.55 live RM 5.1 report; exact trigger/action
    # meanings are *not* assumed from these settings-family names.
    settings = {
        "onOffSwitch.3": {device: "SENSITIVE_LABEL" if secrets else "Light"},
        "tCapab33": "Periodic Schedule",
        "startingA22": "01:00",
        "endingA22": "07:00",
        "selectHoursC33": "1,2,3",
    }
    if secrets:
        settings["apiToken"] = "SENSITIVE_TOKEN"
        settings["destinationUrl"] = "https://private.example/?token=SENSITIVE_TOKEN"
        settings["onOffSwitch.4"] = {"https://bad.example": "malicious", "0": "invalid"}
    return {"success": True, "app": {"id": int(ident), "type": "Rule-5.1"},
            "page": {"sections": []}, "settings": settings,
            "settingsRedactionNote": "safe server-side redaction"}


def test_rm_parser_allowlist_and_no_sensitive_values():
    result = interpret_rm_settings(rm_payload(), "3992")
    assert result["rmSettingsInspected"] is True
    assert result["rmReferenceDeviceIds"] == ["7841"]
    assert result["rmKeyFamilyCounts"]["device_reference"] == 2
    assert result["rmKeyFamilyCounts"]["trigger_capability"] == 1
    assert result["rmKeyFamilyCounts"]["time_or_schedule"] == 3
    assert result["rmActionTargetsVerified"] is False
    assert result["rmTriggerLogicVerified"] is False
    for secret in ("SENSITIVE_", "private.example", "01:00", "Periodic Schedule"):
        assert secret not in str(result)


def test_rm_parser_wrong_id_or_app_family_fails_closed():
    assert not interpret_rm_settings(rm_payload(), "3931")["rmSettingsInspected"]
    other = rm_payload()
    other["app"]["type"] = "Room Lights"
    assert not interpret_rm_settings(other, "3992")["rmSettingsInspected"]
    assert not is_rule_machine_app({"type": "Unknown", "name": "Big Lamp"})
    assert is_rule_machine_app({"type": "Rule-5.1", "name": "Bedroom 3 light"})
    assert not interpret_rm_settings({"app": {"id": 3992},
                                      "settings": {"onOffSwitch.3": {"7841": "X"}}},
                                     "3992")["rmSettingsInspected"]


def test_rm_settings_device_ref_is_not_a_verified_action_overlap():
    first = {"id": "3992", "configVerified": True, **interpret_rm_settings(rm_payload(), "3992")}
    second = {"id": "3931", "configVerified": True,
              **interpret_rm_settings(rm_payload("3931", "7841"), "3931")}
    comparison = analyse_dependency_probes([first, second])
    assert comparison["typedActionDeviceOverlaps"] == []
    assert comparison["rmDeviceReferenceMatches"][0]["deviceIds"] == ["7841"]
    assert comparison["historicalExecutionVerified"] is False


def inventory():
    rows = [
        ("3892", "OwnTracks", "disabled", "app"),
        ("3951", "Power saving: Livingroom Nest Mini", "disabled", "app"),
        ("4011", "Lighting Automation Heartbeat", "active", "app"),
        ("3992", "Bedroom 3 lamp off", "active", "Rule-5.1"),
        ("3931", "Big Lamp scheduled OFF", "active", "Rule-5.1"),
        ("4206", "Bedroom 3 Light Mode Controller", "active", "app"),
        ("3062", "Hallway dimmer", "active", "app"),
    ]
    return {"total": len(rows), "inventory_identities": [
        {"id": ident, "name": name, "status": status, "type": kind}
        for ident, name, status, kind in rows]}


def jobs():
    return {"status": "parsed",
            "candidateIdsByType": {"app": ["3892", "3951", "3931", "3992"]}}


class FakeMCP:
    def __init__(self, *, invalid_dependents=False):
        self.calls = []
        self.active = 0
        self.peak = 0
        self.invalid_dependents = invalid_dependents

    async def list_tools(self):
        return [SimpleNamespace(name="hub_read_apps_code")]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(.001)
            tool, args = arguments["tool"], arguments["args"]
            assert name == "hub_read_apps_code"
            if tool == "hub_get_app_config":
                ident = str(args["appId"])
                if args["includeSettings"] is True:
                    assert ident in ("3992", "3931")
                    return SimpleNamespace(is_error=False, data=rm_payload(
                        ident, "7841" if ident == "3992" else "7827"))
                return SimpleNamespace(is_error=False, data={
                    "success": True,
                    "app": {"id": int(ident),
                            "type": "Rule-5.1" if ident in ("3992", "3931") else "app"},
                    "page": {"sections": [{"title": "Rule",
                                          "paragraphs": [], "inputs": []}]},
                })
            assert tool == "hub_list_device_dependents"
            assert set(args) == {"deviceId"}  # Regression: NOT appId
            if self.invalid_dependents:
                return SimpleNamespace(is_error=True, data={"success": False})
            ident = "3992" if args["deviceId"] == "7841" else "3931"
            return SimpleNamespace(is_error=False,
                                   data={"success": True,
                                         "appsUsing": [{"id": ident, "disabled": False}]})
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_bounded_rm_second_pass_then_device_dependents():
    mcp = FakeMCP()
    picks = select_automation_probes(inventory(), jobs())
    assert picks[:2][0]["id"] == "3892"
    assert {x["id"] for x in picks if x["type"] == "Rule-5.1"} == {"3992", "3931"}
    report, receipts = await inspect_automation_dependencies(mcp, inventory(), jobs())
    assert mcp.peak <= 2
    assert len(mcp.calls) == 10  # 6 normal, 2 RM, 2 device-dependents
    extra = [x for x in mcp.calls if x[1]["tool"] == "hub_get_app_config"
             and x[1]["args"]["includeSettings"] is True]
    assert {v[1]["args"]["appId"] for v in extra} == {"3992", "3931"}
    assert len([e for e in receipts if
                e["evidence_kind"] == "chat_audit_rm_settings_shape"]) == 2
    assert len([e for e in receipts if
                e["evidence_kind"] == "chat_audit_rm_device_dependents"]) == 2
    assert report["summary"]["rmReferencesObserved"] == 2
    assert report["summary"]["typedActionDeviceOverlaps"] == []
    assert all(not e["actionDirectionVerified"] for e in report["deviceDependentEdges"])
    rendered = render_dependency_findings(report)
    assert "action/trigger direction unverified" in rendered
    assert "Dependency index corroboration" in rendered
    for secret in ("SENSITIVE_", "private.example"):
        assert secret not in str(report)
        assert secret not in str(receipts)
        assert secret not in rendered


@pytest.mark.asyncio
async def test_failed_dependency_index_does_not_invent_edges():
    report, receipts = await inspect_automation_dependencies(
        FakeMCP(invalid_dependents=True), inventory(), jobs())
    assert report["deviceDependentEdges"] == []
    assert all(not e["success"] for e in receipts if
               e["evidence_kind"] == "chat_audit_rm_device_dependents")


@pytest.mark.asyncio
async def test_zero_budget_stops_all_rm_and_dependent_reads():
    mcp = FakeMCP()
    report, receipts = await inspect_automation_dependencies(
        mcp, inventory(), jobs(), max_elapsed=0.0)
    assert mcp.calls == []
    assert receipts == []
    assert report["summary"]["rmReferencesObserved"] == 0
