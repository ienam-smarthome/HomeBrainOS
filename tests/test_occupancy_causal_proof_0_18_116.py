"""0.18.116 regression: sensor correlation is NOT confirmed ghost occupancy.

This reproduces typed event/command metadata from the user's v0.18.115
read-only test, with no Hubitat requests or provider calls.
"""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import sys

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))
from occupancy_causal_proof import guard_unverified_occupancy_cause
from api_response_builder import build_agent_response


def _light_history():
    events = [
        {
            "name": "switch", "value": "off",
            "date": "2026-10-25T17:01:17.095+0000",
            "producedBy": {"type": "device", "id": "7790"},
        },
        {
            "name": "command-off",
            "date": "2026-10-25T17:01:16.922+0000",
            "producedBy": {"type": "app", "id": "4019"},
        },
        {
            "name": "switch", "value": "off",
            "date": "2026-10-25T16:58:58.937+0000",
            "producedBy": {"type": "device", "id": "7790"},
        },
        {
            "name": "command-off",
            "date": "2026-10-25T16:58:58.691+0000",
            "producedBy": {"type": "app", "id": "4019"},
        },
    ]
    return {
        "tool": "homebrain_device_history", "success": True,
        "effect": "read", "mutates": False,
        "details": {
            "label": "Livingroom Light 1", "attribute": "switch",
            "temporalAnalysis": {
                "observedIntervals": [
                    {
                        "start": "2026-10-25T16:30:46.568+0000",
                        "end": "2026-10-25T16:58:58.937+0000",
                        "durationSeconds": 1692,
                    },
                    {
                        "start": "2026-10-25T16:59:15.394+0000",
                        "end": "2026-10-25T17:01:17.095+0000",
                        "durationSeconds": 122,
                    },
                ]
            }, "boundaryEvents": events,
        },
    }


def _motion_history(label, listener):
    triggered = [{"appId": listener, "handler": "motionHandler"}]
    return {
        "tool": "homebrain_device_history", "success": True,
        "effect": "read", "mutates": False,
        "details": {
            "label": label, "attribute": "motion",
            "boundaryEvents": [
                {"name": "motion", "value": "inactive",
                 "date": "2026-10-25T17:00:41.163+0000",
                 "triggered": triggered},
                {"name": "motion", "value": "active",
                 "date": "2026-10-25T16:59:16.111+0000",
                 "triggered": triggered},
            ],
        },
    }


def _receipts():
    return [
        {"tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
         "success": True, "arguments": {
             "tool": "hub_get_app_config", "args": {"appId": "4019"}},
         "summary": "object fields: success, app, page, modeInputs"},
        _light_history(),
        _motion_history("Livingroom Soft Sensor", 4129),
        _motion_history("Linptech Kitchen sensor", 4019),
    ]


BAD = """Based on recorded activity, the most likely cause of the light
staying on is **false motion detection (ghosting)**. The evidence shows
the controlling automation is working exactly as configured; in every
observed instance it turns off about 30 seconds after motion turns inactive.
**Livingroom Soft Sensor** reported inactive at 16:58:29 and
App 4019 issued off() at 16:58:58. Sensors are triggering falsely.
"""


def test_clone_listener_edge_is_not_off_rule_cause():
    message, changed = guard_unverified_occupancy_cause(BAD, _receipts())
    assert changed
    assert "ghosting" not in message
    assert "most likely cause" not in message
    assert "not establish" in message or "not verified" in message
    assert "28m 12s" in message
    assert "App 4019 issued OFF at 16:58:58.691" in message
    assert "0.246s later" in message
    assert "App 4019 issued OFF at 17:01:16.922" in message
    assert "0.173s later" in message
    assert "Livingroom Soft Sensor" in message
    # A subscribed Linptech inactive edge may now be reported as a positive
    # timing correlation; it must NOT be mislabeled an unlinked clone.
    assert "Sensor-source limitation:** The retained motion events for Livingroom Soft Sensor" in message
    assert "cloned sensor" in message


def test_api_serialization_repairs_bad_root_cause_without_erasing_receipts():
    rows = _receipts()
    outcome = SimpleNamespace(
        route="unified-mcp-agent", request_class="live-read",
        message=BAD, evidence=rows,
        metrics={"outcome": "unresolved",
                 "counters": {}, "timings_ms": {}},
        investigation_coverage={"domain": "causal_provenance",
                                "sourceChecksComplete": False},
    )
    response = build_agent_response(
        outcome, model="gemma4:31b", elapsed_ms=55000, version="0.18.116"
    )
    assert response["message"].startswith("**Verified light history:")
    assert response["evidence_validation"]["unverified_occupancy_cause_corrected"]
    assert response["outcome_presentation"]["value"] == "unresolved"
    assert response["evidence"] == rows
    assert response["version"] == "0.18.116"


def test_tentative_hypothesis_is_preserved_without_fabricated_certainty():
    text = "False motion might explain this, but the cause is not verified."
    assert guard_unverified_occupancy_cause(text, _receipts()) == (text, False)


def test_factual_status_and_unrelated_automation_unmodified():
    for text in (
        "Livingroom Light 1 is OFF.",
        "App 4019 issued off() at 16:58:58; switch reported off afterwards.",
        "The garage automations were paused.",
    ):
        assert guard_unverified_occupancy_cause(text, _receipts()) == (text, False)


def test_an_unpaired_command_is_not_reported_as_effect():
    rows = _receipts()
    light = rows[1]
    light["details"]["boundaryEvents"] = [
        e for e in light["details"]["boundaryEvents"]
        if e.get("name") == "command-off"
    ]
    message, changed = guard_unverified_occupancy_cause(BAD, rows)
    assert changed
    assert "Verified OFF commands" not in message
    assert "App 4019 issued OFF" not in message


def test_without_sensor_listeners_avoid_claiming_missing_subscription():
    rows = _receipts()
    rows[2]["details"]["boundaryEvents"] = [
        {"name": "motion", "value": "active"}
    ]
    msg, changed = guard_unverified_occupancy_cause(BAD, rows)
    assert changed
    assert "**Sensor-source limitation:**" not in msg


def test_light_guide_checks_configured_actual_sensors_not_room_clones():
    guidance = (APP / "skills/hubitat-investigator/SKILL.md").read_text()
    assert "configured" in guidance
    assert "Cloned/virtual sensor" in guidance
    assert "Compare event listeners" in guidance
