"""0.18.43: bounded read-only automation dependency probes.

The fixture intentionally reproduces actual MCP app-config page structure and
the previous live scheduler/installed inventory ambiguity.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from automation_dependency_probe import (
    select_automation_probes, summarise_config, analyse_dependency_probes,
    inspect_automation_dependencies, render_dependency_findings,
)
from health_audit_service import render_comprehensive_system_audit, _redact_audit_urls


def installed():
    rows = [
        ("3892", "OwnTracks", "disabled"),
        ("3951", "Power saving: Livingroom Nest Mini", "disabled"),
        ("4011", "Lighting Automation Heartbeat", "active"),
        ("3992", "Bedroom 3 lamp off", "active"),
        ("3931", "Big Lamp scheduled OFF", "active"),
        ("4206", "Bedroom 3 Light Mode Controller", "active"),
        ("4999", "Kitchen Internet Control", "active"),
    ]
    return {"total": len(rows), "inventory_identities": [
        {"id": ident, "name": name, "status": status, "type": "app"}
        for ident, name, status in rows
    ]}


def scheduler():
    return {"status": "parsed", "candidateIdsByType": {
        "app": ["3892", "3951", "3992", "4011", "4206"],
        "device": ["7103"],
    }, "reportedJobs": 272, "rowsExamined": 272,
        "completeRows": True, "ownerIdentifiedRows": 0}


def page(ident, *, label="Livingroom Light 1", device_id=None):
    sections = [{
        "title": "Trigger Events",
        "paragraphs": ["Mode changes to Evening, Sunset"],
        "inputs": [],
    }, {
        "title": "Actions to Run",
        "paragraphs": [f"IF motion is active THEN On: {label} END-IF"],
        "inputs": ([{"type": "device", "deviceId": device_id}]
                   if device_id else []),
    }]
    return {"success": True, "app": {"id": int(ident)},
            "page": {"sections": sections}}


def test_selection_is_bounded_by_fresh_app_ids_and_not_display_name_guesses():
    choices = select_automation_probes(installed(), scheduler())
    assert len(choices) == 6
    assert [x["id"] for x in choices[:2]] == ["3892", "3951"]
    assert choices[2]["id"] == "4011"
    assert {x["id"] for x in choices[3:]} == {"3931", "3992", "4206"}
    assert "4999" not in [x["id"] for x in choices]
    assert not select_automation_probes(installed(), {})
    assert not select_automation_probes({}, scheduler())
    assert not select_automation_probes(installed(), {"status": "unavailable"})


def test_only_typed_ids_from_action_scoped_config_count_as_device_edges():
    a = summarise_config(page("3992", device_id="7339"), "3992")
    b = summarise_config(page("3931", device_id="7339"), "3931")
    assert a["typedActionDeviceIds"] == ["7339"]
    assert b["typedActionDeviceIds"] == ["7339"]
    verdict = analyse_dependency_probes([
        {"id": "3992", **a}, {"id": "3931", **b},
    ])
    assert len(verdict["typedActionDeviceOverlaps"]) == 1
    assert verdict["typedActionDeviceOverlaps"][0]["targetDeviceIds"] == ["7339"]
    assert verdict["historicalExecutionVerified"] is False
    assert verdict["callbackOwnersVerified"] is False


def test_prose_number_and_identical_action_wording_are_only_weak_candidates():
    first = page("3992")
    second = page("3931")
    first["page"]["sections"][1]["paragraphs"] = [
        "THEN On: Livingroom Light 1 (#7339) END-IF"
    ]
    second["page"]["sections"][1]["paragraphs"] = [
        "THEN On: Livingroom Light 1 (#7339) END-IF"
    ]
    data = [
        {"id": "3992", **summarise_config(first, "3992")},
        {"id": "3931", **summarise_config(second, "3931")},
    ]
    outcome = analyse_dependency_probes(data)
    assert outcome["typedActionDeviceOverlaps"] == []
    assert len(outcome["textOnlyActionCandidates"]) == 1
    assert "identity unverified" in outcome["textOnlyActionCandidates"][0]["proof"]
    assert "Not proof" not in render_dependency_findings({
        "selected": data, "attempts": data, "summary": outcome,
    })  # wording is explicitly 'unverified'


def test_config_mismatch_and_raw_text_do_not_prove_action_devices():
    assert summarise_config(page("3992"), "3951") is None
    assert summarise_config({"success": True, "app": {"id": 3992},
                              "settings": {"actions": [{"deviceId": 7339}]}},
                             "3992") is None
    data = page("3992")
    data["page"]["sections"][1]["paragraphs"].append(
        "https://private.example/?lat=51.44&lon=-0.01&token=SECRET"
    )
    data["page"]["sections"][1]["inputs"].append({
        "type": "password", "title": "Token", "value": "SECRET",
    })
    summary = summarise_config(data, "3992")
    assert summary["typedActionDeviceIds"] == []
    assert "SECRET" not in str(summary)
    assert "private.example" not in str(summary)
    assert "51.44" not in str(summary)


def test_no_false_overlap_without_action_text_or_exact_shared_targets():
    a = summarise_config(page("3992", label="Kitchen Main Light", device_id="7000"), "3992")
    b = summarise_config(page("3931", label="Bedroom Light", device_id="7339"), "3931")
    assert not analyse_dependency_probes([
        {"id": "3992", **a}, {"id": "3931", **b},
    ])["typedActionDeviceOverlaps"]


class FakeMCP:
    def __init__(self, *, has_gateway=True, fail=None):
        self.has_gateway = has_gateway
        self.fail = fail
        self.calls = []
        self.concurrency = 0
        self.peak = 0

    async def list_tools(self):
        return [SimpleNamespace(name="hub_read_apps_code")] if self.has_gateway else []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        self.concurrency += 1
        self.peak = max(self.peak, self.concurrency)
        try:
            assert name == "hub_read_apps_code"
            assert arguments["tool"] == "hub_get_app_config"
            assert set(arguments["args"]) == {"appId", "includeSettings"}
            assert arguments["args"]["includeSettings"] is False
            await asyncio.sleep(0.001)
            ident = arguments["args"]["appId"]
            if ident == self.fail:
                return SimpleNamespace(is_error=True, data={"success": False})
            data = page(ident, device_id="7339" if ident in ("3992", "3931") else None)
            return SimpleNamespace(is_error=False, data=data)
        finally:
            self.concurrency -= 1


@pytest.mark.asyncio
async def test_one_bounded_batch_positive_reads_exact_receipts_and_comparison():
    mcp = FakeMCP(fail="3951")
    report, receipts = await inspect_automation_dependencies(
        mcp, installed(), scheduler(), checked_at="2026-10-19T14:44:00+00:00",
    )
    assert len(mcp.calls) == 6
    assert mcp.peak <= 2
    assert all(name == "hub_read_apps_code" for name, _ in mcp.calls)
    assert len(receipts) == 6
    assert all(x["mutates"] is False and x["effect"] == "read" for x in receipts)
    assert all(x["sub_tool"] == "hub_get_app_config" for x in receipts)
    assert all(x["evidence_kind"] == "chat_audit_app_dependency_configuration" for x in receipts)
    assert report["summary"]["configurationReadsVerified"] == 5
    assert len(report["summary"]["typedActionDeviceOverlaps"]) == 1
    assert report["summary"]["typedActionDeviceOverlaps"][0]["appIds"] == ["3931", "3992"]
    rendered = render_dependency_findings(report)
    assert "configuration pages verified" in rendered
    assert "matching typed action-device IDs" in rendered
    assert "callback ownership" in rendered
    assert "raw settings" in rendered


@pytest.mark.asyncio
async def test_no_gateway_and_empty_candidate_set_fail_closed():
    mcp = FakeMCP(has_gateway=False)
    report, receipts = await inspect_automation_dependencies(mcp, installed(), scheduler())
    assert report["sourceStatus"] == "gateway-unavailable"
    assert mcp.calls == []
    assert receipts == []
    missing, receipts = await inspect_automation_dependencies(mcp, {}, scheduler())
    assert missing["selected"] == []
    assert receipts == []


@pytest.mark.asyncio
async def test_budget_exhaustion_skips_mcp_without_writes():
    mcp = FakeMCP()
    report, _ = await inspect_automation_dependencies(
        mcp, installed(), scheduler(), max_elapsed=0,
    )
    assert report["summary"]["configurationReadsVerified"] == 0
    assert mcp.calls == []


def test_audit_report_integrates_dependency_section_as_unverified_when_missing():
    snap = {"checked_at": "2026-10-19T14:44:00+00:00",
            "issues": [], "sections": {
                "automations": installed(),
                "devices": {"total": 205, "offline": [], "no_recent_activity": []},
                "logs": {"available": True, "entries_checked": 10},
            }}
    rendered = render_comprehensive_system_audit(
        snap, None, scheduled_jobs=scheduler(),
    )
    assert "### Automation configuration and dependency investigation" in rendered
    assert "Not checked" in rendered
    assert "No repairs performed" in rendered


def test_audit_log_privacy_redacts_coordinates_and_credentials():
    raw = ("OpenWeatherMap request failed for URL "
           "https://api.openweathermap.org/data/4.0/onecall?"
           "lat=51.466483&lon=-0.018197&appid=SENSITIVE123: Read timed out.")
    cleaned = _redact_audit_urls(raw)
    assert "OpenWeatherMap request failed" in cleaned
    assert "Read timed out" in cleaned
    assert "[URL redacted]" in cleaned
    for sensitive in ("51.466483", "-0.018197", "SENSITIVE123",
                      "api.openweathermap.org"):
        assert sensitive not in cleaned

    snapshot = {"checked_at": "2026-10-19T14:44:00+00:00",
                "issues": [{"severity": "warning", "title": "Weather error",
                            "detail": raw}],
                "sections": {
                    "devices": {"total": 1, "offline": [], "no_recent_activity": []},
                    "automations": {"total": 1},
                    "logs": {"available": True, "entries_checked": 1},
                }}
    whole_report = render_comprehensive_system_audit(snapshot, None)
    assert "Read timed out" in whole_report
    assert "[URL redacted]" in whole_report
    assert "51.466483" not in whole_report
    assert "SENSITIVE123" not in whole_report
