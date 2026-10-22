"""0.18.58: choose a related lighting rule pair without treating names as proof."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from automation_dependency_probe import (
    select_rm_settings_probes, inspect_automation_dependencies,
)


def row(ident, name, reason="lighting dependency comparison candidate"):
    return {
        "id": str(ident), "name": name, "type": "rule",
        "reason": reason, "configVerified": True, "rmAppTypeVerified": True,
        "typedActionDeviceIds": [],
    }


def test_v01857_live_candidates_choose_same_subject_not_lowest_two_ids():
    selected = select_rm_settings_probes([
        row(3600, "Lighting: bedroom 3 low light"),
        row(3602, "Lighting: livingroom low light"),
        row(3931, "Lighting: Auto OFF - Big Lamp"),
        row(3992, "Lighting: Auto OFF - Bedroom 3 Light"),
    ])
    assert [x["id"] for x in selected] == ["3600", "3992"]
    assert all(x["typedActionDeviceIds"] == [] for x in selected)


def test_unrelated_candidates_keep_bounded_numeric_fallback():
    items = [row(3931, "Big lamp off"), row(3602, "Livingroom low light"),
             row(3600, "Bedroom 3 low light")]
    assert [x["id"] for x in select_rm_settings_probes(items)] == ["3600", "3602"]


def test_name_similarity_not_device_evidence_and_wrong_types_fail_closed():
    first = row(3600, "Bedroom 3 Light")
    second = row(3992, "Bedroom 3 Light")
    second["rmAppTypeVerified"] = False
    second["type"] = "app"
    assert [x["id"] for x in select_rm_settings_probes([first, second])] == ["3600"]
    first["typedActionDeviceIds"] = ["7841"]
    assert select_rm_settings_probes([first, second]) == []


class FakeHub:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [SimpleNamespace(name="hub_read_apps_code")]

    async def call_tool(self, name, arguments):
        assert name == "hub_read_apps_code"
        assert arguments["tool"] in {
            "hub_get_app_config", "hub_list_device_dependents"
        }
        self.calls.append(arguments)
        leaf, args = arguments["tool"], arguments["args"]
        if leaf == "hub_list_device_dependents":
            assert set(args) == {"deviceId"}
            ident = str(args["deviceId"])
            return SimpleNamespace(is_error=False, data={
                "success": True,
                "appsUsing": [{"id": 3600}, {"id": 3992}] if ident == "7841" else [],
            })
        ident = str(args["appId"])
        settings = (
            {"settings": {"onOffSwitch.3": {
                "7841" if ident in {"3600", "3992"} else "7805": "Private label"
            }}} if args["includeSettings"] else {}
        )
        return SimpleNamespace(is_error=False, data={
            "success": True, "app": {"id": int(ident), "type": "Rule-5.1"},
            "page": {"sections": [{"title": "Overview", "inputs": [], "paragraphs": []}]},
            **settings,
        })


@pytest.mark.asyncio
async def test_live_style_bounded_two_settings_reads_corroborate_real_ids():
    items = [
        ("3892", "OwnTracks", "disabled", "app"),
        ("3951", "Power saving: Livingroom Nest Mini", "disabled", "app"),
        ("3600", "Lighting: bedroom 3 low light", "active", "rule"),
        ("3602", "Lighting: livingroom low light", "active", "rule"),
        ("3931", "Lighting: Auto OFF - Big Lamp", "active", "rule"),
        ("3992", "Lighting: Auto OFF - Bedroom 3 Light", "active", "rule"),
    ]
    installed = {"inventory_identities": [
        {"id": id_, "name": name, "status": status, "type": kind}
        for id_, name, status, kind in items]}
    scheduler = {"status": "parsed", "candidateIdsByType": {
        "app": ["3892", "3951", "3600", "3602", "3931", "3992"],
    }}
    hub = FakeHub()
    result, receipts = await inspect_automation_dependencies(hub, installed, scheduler)
    ordinary = [c for c in hub.calls if c["tool"] == "hub_get_app_config"
                and c["args"]["includeSettings"] is False]
    deeper = [c for c in hub.calls if c["tool"] == "hub_get_app_config"
              and c["args"]["includeSettings"] is True]
    assert len(ordinary) == 6
    assert {str(x["args"]["appId"]) for x in deeper} == {"3600", "3992"}
    assert all(x["tool"] != "hub_set_rule" for x in hub.calls)
    assert result["summary"]["typedActionDeviceOverlaps"] == []
    assert result["summary"]["rmDeviceReferenceMatches"][0]["deviceIds"] == ["7841"]
    assert result["summary"]["historicalExecutionVerified"] is False
    assert "Private label" not in str(result)
    assert "Private label" not in str(receipts)
