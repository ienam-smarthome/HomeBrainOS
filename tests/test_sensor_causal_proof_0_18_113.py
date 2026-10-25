"""0.18.113: model explanations may not invent a proven sensor blocker.

Simulated typed Hubitat receipts; absolutely no live device calls.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from sensor_causal_claim_guard import guard_unverified_sensor_blocker
from interval_duration_guard import guard_interval_table_durations
from api_response_builder import build_agent_response


def _receipts():
    return [
        {
            "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
            "success": True, "effect": "read", "mutates": False,
            "arguments": {"tool": "hub_get_app_config", "args": {"appId": "4019"}},
            "summary": "object fields: success, app, page, modeInputs",
        },
        {
            "tool": "hub_read_devices", "sub_tool": "hub_list_devices",
            "success": True, "effect": "read", "mutates": False,
            "arguments": {"tool": "hub_list_devices", "args": {"roomFilter": "Living Room"}},
            "summary": "room inventory with 17 devices",
        },
        {
            "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
            "success": True, "effect": "read", "mutates": False,
            "arguments": {"tool": "hub_get_logs", "args": {"appId": "4019", "since": "24h"}},
            "details": {"logCount": 1, "logs": [
                {"message": "app|4019|Livingroom Light 1: mode -> Late afternoon"},
            ]},
        },
        {
            "tool": "homebrain_read_groovy_source", "sub_tool": None,
            "success": True, "effect": "read", "mutates": False,
            "arguments": {"appId": "4019",
                          "symbols": ["motion", "inactive", "keepOn", "offTimer"]},
            "details": {
                "fullImplementationVerified": True,
                "verifiedCharacters": 186457,
                "declaredTotalCharacters": 186457,
            },
        },
        {
            "tool": "homebrain_device_history", "success": True,
            "effect": "read", "mutates": False,
            "arguments": {"name": "Livingroom Light 1", "attribute": "switch"},
            "details": {
                "label": "Livingroom Light 1",
                "temporalAnalysis": {
                    "observedIntervals": [
                        {
                            "start": "2026-10-24T20:23:10.850+0100",
                            "end": "2026-10-25T00:41:40.447+0100",
                            "durationSeconds": 15510,
                        },
                        {
                            "start": "2026-10-25T12:13:54.150+0000",
                            "end": "2026-10-25T12:14:15.260+0000",
                            "durationSeconds": 21,
                        },
                    ],
                    "intervalCount": 2, "totalActiveSeconds": 15531,
                    "totalActiveDuration": "4h 19m",
                },
            },
        },
    ]


DRAFT = """The most likely cause for **Livingroom Light 1** staying ON is
**ghost occupancy** reported by **Livingroom Soft Sensor (ID: 7766)**.
The Livingroom Soft Sensor is currently active and blocks the off-timer
from running whenever the room is empty.

| Start State (Time) | End State (Time) | Duration | Note |
| --- | --- | --- | --- |
| **ON** (Oct 24, 20:23) | **OFF** (Oct 25, 00:41) | ~3h 18m | Long duration |
| **ON** (Oct 25, 12:13) | **OFF** (Oct 25, 12:14) | 21s | Rapid cycle |
"""


def test_full_source_and_room_inventory_do_not_prove_named_sensor_block():
    corrected, changed = guard_unverified_sensor_blocker(DRAFT, _receipts())
    assert changed
    assert "Possible cause, not verified" in corrected
    assert "Livingroom Soft Sensor (ID 7766)" in corrected
    assert "not independently establish" in corrected
    assert "4h 18m 30s" in corrected
    assert "complete source retrieval" in corrected.lower()
    assert "ghost occupancy" not in corrected
    assert "is currently active" not in corrected


def test_tabular_interval_error_is_corrected_without_changing_other_rows():
    corrected, changed = guard_interval_table_durations(DRAFT, _receipts())
    assert changed
    assert "| 4h 18m 30s | Long duration |" in corrected
    assert "| 21s | Rapid cycle |" in corrected
    assert "Livingroom Soft Sensor" in corrected


def test_no_repair_for_valid_rounded_minutes():
    source = DRAFT.replace("~3h 18m", "~4h 19m")
    corrected, changed = guard_interval_table_durations(source, _receipts())
    assert not changed
    assert corrected == source


def test_direct_sensor_state_and_explicit_block_log_preserve_supported_claim():
    rows = _receipts()
    rows.append({
        "tool": "hub_read_devices", "sub_tool": "hub_get_device",
        "success": True, "effect": "read", "mutates": False,
        "arguments": {"tool": "hub_get_device", "args": {"deviceId": "7766"}},
        "details": {"reportedDeviceState": {
            "deviceId": "7766",
            "reportedAttributes": {"motion": "active"}
        }},
    })
    rows[2]["details"]["logs"].append({
        "message": "app|4019|Livingroom Soft Sensor 7766 blocks off-timer"
    })
    unchanged, changed = guard_unverified_sensor_blocker(DRAFT, rows)
    assert not changed
    assert unchanged == DRAFT


def test_noncausal_state_answer_unchanged():
    text = "Livingroom Light 1 is currently OFF."
    assert guard_unverified_sensor_blocker(text, _receipts()) == (text, False)
    assert guard_interval_table_durations(text, _receipts()) == (text, False)


def test_final_api_response_calibrates_the_same_live_draft():
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message=DRAFT, evidence=_receipts(),
        metrics={"outcome": "unresolved",
                 "counters": {}, "timings_ms": {}},
        investigation_coverage={"domain": "causal_provenance",
                                "evidenceComplete": False},
    )
    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=62974, version="0.18.113"
    )
    assert "Possible cause, not verified" in response["message"]
    assert "3h 18m" not in response["message"]
    assert response["evidence_validation"]["unverified_sensor_blocker_corrected"]
    assert response["evidence_validation"]["interval_table_duration_corrected"]
    assert response["outcome_presentation"]["value"] == "unresolved"
