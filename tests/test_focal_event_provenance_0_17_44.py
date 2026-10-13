"""0.17.44: original manual incident versus newest unrelated state event.

Cross-source evidence from 12–13 Oct 2026:
  native Living Room Button (746) button 1 pushed at 23:49:27.303+01,
  button automation app 1251 issued OFF at 23:49:27.336+01,
  light 7805 physically reported OFF at 23:49:27.529+01,
  but a *newer* OFF on 13 Oct 08:43:44 lacked a matching manual command.
Do not conflate these events. Never interpret requested BST time as UTC.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from datetime import datetime
from focal_event_provenance import (
    current_config_facts, explicit_requested_instant, off_candidates,
    physical_button_observations, select_focal_off, source_offset_for_request,
)
from motion_lockout_investigation import prefetch_motion_lockout


def light_history():
    return {
        "temporalAnalysis": {"intervals": [
            {"start": "2026-10-12T23:49:19.140+0100",
             "end": "2026-10-12T23:49:27.529+0100"},
            {"start": "2026-10-13T07:52:12.483+0100",
             "end": "2026-10-13T08:43:44.028+0100"},
        ]},
        "commandEvents": [{
            "name": "command-off",
            "date": "2026-10-12T23:49:27.336+0100",
            "producedBy": {"id": "1251", "type": "app",
                           "label": "button 1 pushed"},
        }],
        "boundaryEvents": [
            {"name": "switch", "value": "off",
             "date": "2026-10-13T08:43:44.028+0100",
             "producedBy": {"id": "7790", "type": "device"}},
            {"name": "switch", "value": "off",
             "date": "2026-10-12T23:49:27.529+0100",
             "producedBy": {"id": "7790", "type": "device"}},
        ],
    }


def physical_button():
    return {
        "observedEvents": [
            {"name": "pushed", "value": "1", "type": "physical",
             "date": "2026-10-12T23:49:27.303+0100",
             "producedBy": {"id": "746", "type": "device"}},
            {"name": "pushed", "value": "2", "type": "physical",
             "date": "2026-10-12T23:49:28.477+0100",
             "producedBy": {"id": "746", "type": "device"}},
        ],
    }


def test_latest_off_and_latest_verified_manual_off_are_different():
    data = light_history()
    pushes = physical_button_observations(physical_button(), "746")
    assert len(off_candidates(data)) == 2
    result = select_focal_off(
        data, "Investigate the latest manual OFF of Livingroom Light 1 followed by motion",
        physical_presses=pushes,
    )
    assert result["latestObservedOff"] == "2026-10-13T07:43:44.028000+00:00"
    assert result["selectedOff"] == "2026-10-12T22:49:27.529000+00:00"
    assert result["manualOffVerified"] is True
    assert result["newerNonManualOffObserved"] is True
    chain = result["physicalButtonCommandChain"][0]
    assert chain["button"]["buttonNumber"] == "1"
    assert chain["buttonToCommandMs"] == 33.0
    assert chain["commandToStateMs"] == 193.0
    assert chain["commandProducer"]["id"] == "1251"
    assert not chain["automationLockoutExecutionVerified"]


def test_latest_off_without_manual_requirement_does_not_select_earlier_button():
    result = select_focal_off(
        light_history(), "Explain latest OFF for Livingroom Light 1",
        physical_presses=physical_button_observations(physical_button(), "746"),
    )
    assert result["selectedOff"].startswith("2026-10-13T07:43:44")
    assert result["manualOffVerified"] is False


def test_no_physical_press_never_promotes_button_app_label():
    result = select_focal_off(
        light_history(), "latest manual OFF", physical_presses=[],
    )
    assert result["manualOffVerified"] is False
    assert result["selectedOff"].startswith("2026-10-13")
    assert result["physicalButtonCommandChain"] == []


def test_wrong_number_button_cannot_be_misattributed_as_manual_press():
    rows = physical_button_observations(physical_button(), "746")
    rows = [x for x in rows if x["buttonNumber"] == "2"]
    result = select_focal_off(light_history(), "latest manual OFF",
                              physical_presses=rows)
    assert not result["manualOffVerified"]


def test_explicit_wall_clock_offset_source_is_utc_normalized():
    source = source_offset_for_request(
        light_history(), "Investigate OFF at approximately 23:49:27 on 12 October 2026",
    )
    assert source == "2026-10-12T23:49:27.529+01:00"
    request = "Investigate OFF at approximately 23:49:27 on 12 October 2026"
    instant = explicit_requested_instant(request, source)
    assert instant.isoformat() == "2026-10-12T22:49:27+00:00"
    result = select_focal_off(light_history(), request, source_local=source)
    assert result["selectedOff"] == "2026-10-12T22:49:27.529000+00:00"
    assert result["explicitTargetUtc"] == "2026-10-12T22:49:27+00:00"


def test_explicit_time_fails_closed_without_source_offset_or_matching_event():
    query = "Investigate OFF at 23:49:27 on 12 October 2026"
    result = select_focal_off(light_history(), query, source_local=None)
    assert result["selectedOff"] is None
    assert result["status"] == "unresolved-request-clock"
    wrong = select_focal_off(light_history(), query, source_local="2026-10-12T23:49:27+00:00")
    assert wrong["selectedOff"] is None


def test_source_offset_must_match_requested_day_to_prevent_dst_assumption():
    data = light_history()
    query = "Investigate OFF at approximately 23:49:27 on 20 October 2026"
    assert source_offset_for_request(data, query) is None
    assert select_focal_off(data, query, source_local=None)["selectedOff"] is None


def test_current_stored_setting_is_not_the_user_expectation_or_historical_proof():
    facts = current_config_facts({
        "settings": {
            "motionOffLockoutMinutes": "300",
            "motionOffLockoutTrigger": "toggleButtonOnly",
            "password": "private-do-not-include",
        },
        "page": {"sections": [{"title": "Rule Basics"}]},
    })
    assert facts["configuredDurationSeconds"] == 18000
    assert facts["configuredDurationMinutes"] == 300
    assert facts["triggerMode"] == "toggleButtonOnly"
    assert facts["notHistoricalConfigurationProof"] is True
    assert "private-do-not-include" not in json.dumps(facts)
    assert current_config_facts({"page": {"text": "Manual-off lockout: 300 min"}})[
        "configuredDurationMinutes"] is None


def test_end_to_end_history_selects_button_off_and_uses_utc_bounded_logs():
    light = {
        "id": "7805", "name": "Livingroom Light 1", "label": "Livingroom Light 1",
        "room": "Living Room", "attributes": {"switch": "off"},
    }
    button = {
        "id": "746", "name": "🔢 Living Room Button",
        "label": "🔢 Living Room Button", "room": "Button Controllers",
        "attributes": {"pushed": "1"}, "capabilities": ["PushableButton"],
    }
    config = {
        "settings": {
            "motionOffLockoutMinutes": "300",
            "motionOffLockoutTrigger": "toggleButtonOnly",
        },
        "page": {"sections": [{
            "title": "Current Status",
            "inputs": [{
                "title": "Lockout controller",
                "value": "🔢 Living Room Button",
            }],
        }]},
    }
    calls, receipts = [], []

    class MCP:
        async def get_device_identities(self):
            return [light, button]

    class Executor:
        async def execute(self, name, args, **kwargs):
            calls.append((name, args))
            if name == "homebrain_device_history":
                data = physical_button() if args["attribute"] == "pushed" else light_history()
            elif args.get("tool") == "hub_get_app_config":
                assert args["args"]["includeSettings"] is True
                data = config
            elif args.get("tool") == "hub_get_logs":
                data = {"logs": []}
            else:
                raise AssertionError((name, args))
            return SimpleNamespace(success=True, result=SimpleNamespace(data=data))

    class Evidence:
        def record(self, name, args, **kwargs):
            receipts.append({"tool": name, "details": kwargs.get("details")})

    class Catalog:
        def declared_tool(self, name):
            return object()

    host = SimpleNamespace(mcp=MCP(), executor=Executor(),
                           evidence=Evidence(), historical_journal=None)
    messages = []
    query = ("Investigate latest manual OFF of Livingroom Light 1 "
             "followed by motion. Did app 4019's three-minute lockout engage?")
    assert asyncio.run(prefetch_motion_lockout(
        host, query, catalog=Catalog(), messages=messages,
    ))
    result = next(x["details"] for x in receipts
                  if x["tool"] == "homebrain_motion_lockout_investigation")
    assert result["focalSelection"]["manualOffVerified"] is True
    assert result["focalSelection"]["newerNonManualOffObserved"] is True
    assert result["currentConfiguration"]["configuredDurationMinutes"] == 300
    assert result["decisionClaimReconciliation"]["configurationVsRequested"] == [
        {"requestedSeconds": 180, "configuredSeconds": 18000, "matches": False}
    ]
    log_call = next(args["args"] for name, args in calls
                    if args.get("tool") == "hub_get_logs")
    assert log_call["since"].startswith("2026-10-12T22:49:07")
    assert log_call["until"].startswith("2026-10-12T22:52:42")
    assert log_call["appId"] == "4019"
    assert result["lockoutExecutionVerified"] is False
    assert len([x for x in calls if x[0] == "homebrain_device_history"]) == 2
