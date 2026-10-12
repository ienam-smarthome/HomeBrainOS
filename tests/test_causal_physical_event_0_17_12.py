"""General physical-bridge causality and exact-subject prefetch regression tests.

The source example was a bedroom light whose reporting bridge had already
published ON when its dimmer's button event was recorded 82 ms later; Hubitat
then sent a setLevel command as a reaction. Never equate the reporter, the
button, and the downstream app's separate control command.
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_subject_prefetch import causal_subject_seed  # noqa: E402
from causal_timeline import (  # noqa: E402
    explicitly_focused_event_rows, has_explicit_focal_clock
)
from causal_native_logs import causal_boundary_log_windows  # noqa: E402
from causal_evidence_graph import (  # noqa: E402
    build_causal_evidence_graph, needs_mode_history,
    supports_one_pass_deep_synthesis,
)


QUESTION = (
    "Investigate thoroughly why Example Room Light turned on at 08:16 on 12 "
    "October. Check the controlling app, configured triggers, actual sensor "
    "events, app execution logs and possible alternative causes. Read-only."
)


def _identity(label, device_id, **kwargs):
    return {
        "id": device_id,
        "label": label, "name": label, "room": kwargs.get("room", "Example Room"),
        "attributes": {"switch": "off"}, "capabilities": ["Switch"],
        "commands": ["on", "off"],
    }


def _base_history():
    intervals = [
        {
            "start": "2026-10-12T07:25:37.658+0100",
            "end": "2026-10-12T08:03:16.616+0100",
            "durationSeconds": 2259,
        },
        {
            "start": "2026-10-12T08:04:11.131+0100",
            "end": "2026-10-12T08:06:33.954+0100",
            "durationSeconds": 143,
        },
        {
            "start": "2026-10-12T08:10:42.971+0100",
            "end": "2026-10-12T08:14:55.656+0100",
            "durationSeconds": 253,
        },
        {
            "start": "2026-10-12T08:16:10.861+0100",
            "end": "2026-10-12T08:18:23.830+0100",
            "durationSeconds": 133,
        },
    ]
    events = [{
        "name": "switch", "value": "on",
        "date": "2026-10-12T08:16:10.861+0100",
        "type": "physical",
        "triggered": [
            {"appId": 4015, "handler": "lightSwitchHandler"},
            {"appId": 4129, "handler": "liveDeviceEventHandler"},
        ],
        "producedBy": {
            "id": "7790", "label": "Matter Hue Bridge Pro", "type": "device",
        },
    }]
    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Example Room Light", "attribute": "switch",
            "room": "Example Room",
            "temporalAnalysis": {"intervalCount": 4, "observedIntervals": intervals},
            "boundaryEvents": events,
            "observedEvents": events,
            "commandEvents": [],
        },
    }]


def _physical_evidence(*, include_post=True, include_mode=True, app_config=True):
    rows = _base_history()
    rows.append({
        "tool": "homebrain_causal_secondary_correlation",
        "success": True,
        "details": {
            "subject": "Example Room Light",
            "controllers": [{
                "label": "Example Hue dimmer 1", "attribute": "pushed",
                "relevantAlignments": [
                    {
                        "boundaryRole": "start",
                        "subjectTransition": "2026-10-12T08:04:11.131+0100",
                        "controllerEvent": "2026-10-12T08:04:11.252+0100",
                        "signedDeltaSeconds": .121,
                        "eventValue": "1",
                    },
                    {
                        "boundaryRole": "start",
                        "subjectTransition": "2026-10-12T08:10:42.971+0100",
                        "controllerEvent": "2026-10-12T08:10:43.117+0100",
                        "signedDeltaSeconds": .146,
                        "eventValue": "1",
                    },
                    {
                        "boundaryRole": "start",
                        "subjectTransition": "2026-10-12T08:16:10.861+0100",
                        "controllerEvent": "2026-10-12T08:16:10.943+0100",
                        "signedDeltaSeconds": .082,
                        "eventValue": "1",
                    },
                ],
            }],
            "sensors": [{
                "label": "Example FP300", "attribute": "motion",
                "relevantCorrelations": [],
                "oppositeCorrelations": [{
                    "boundaryRole": "end",
                    "subjectTransition": "2026-10-12T08:18:23.830+0100",
                    "sensorEvent": "2026-10-12T08:18:23.620+0100",
                    "signedDeltaSeconds": -.210,
                    "eventValue": "inactive",
                    "attribute": "motion",
                    "producedBy": {
                        "type": "device", "label": "Matter Aqara M3", "id": "7718",
                    },
                }],
            }],
        },
    })
    if include_post:
        rows.append({
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True,
            "arguments": {
                "tool": "hub_list_device_events",
                "args": {
                    "deviceId": "7840", "attribute": "command-setLevel",
                },
            },
            "details": {
                "label": "Example Room Light",
                "attribute": "command-setLevel",
                "events": [{
                    "name": "command-setLevel",
                    "date": "2026-10-12T08:16:10.912+0100",
                    "description": "Command called: setLevel(45)",
                    "producedBy": {
                        "id": "4015", "label": "Example Lighting Mode Controller",
                        "type": "app",
                    },
                }],
            },
        })
    if app_config:
        rows.append({
            "tool": "hub_read_apps_code", "sub_tool": "hub_get_app_config",
            "success": True,
            "arguments": {"tool": "hub_get_app_config", "args": {
                "appId": "4015", "includeSettings": False,
            }},
            "details": {
                "appId": "4015",
                "configured": [
                    "Manual/external turn-on reapply enabled",
                    "School Run mode level 45%; mode changes",
                ],
            },
        })
    rows.append({
        "tool": "hub_read_diagnostics", "sub_tool": "hub_get_logs",
        "success": True,
        "arguments": {"tool": "hub_get_logs", "args": {
            "appId": "4015",
            "since": "2026-10-12T07:15:58.000Z",
            "until": "2026-10-12T07:16:17.000Z",
        }},
        "details": {"logCount": 0, "execution": []},
    })
    if include_mode:
        rows.append({
            "tool": "hub_read_devices", "sub_tool": "hub_list_device_events",
            "success": True,
            "evidence_kind": "authoritative_location_event_history",
            "details": {"events": [{
                "name": "mode", "value": "School Run",
                "date": "2026-10-12T07:15:01+0100",
            }]},
        })
    return rows


def test_unique_full_device_name_beats_short_room_label_in_dense_inventory():
    device_list = [
        _identity("Example Room", "100"),
        _identity("Example Room Light", "7840"),
        _identity("Example Room Light 2", "7841"),
        _identity("Example Room dimmer 1", "7836"),
    ]
    seed = causal_subject_seed(QUESTION, device_list)
    assert seed and seed.name == "Example Room Light"
    assert seed.target["id"] == "7840"


def test_equally_specific_or_numbered_other_devices_remain_ambiguous():
    duplicate = [
        _identity("Example Room Light", "7840"),
        _identity("Example Room Light", "9999"),
    ]
    assert causal_subject_seed(QUESTION, duplicate) is None
    assert causal_subject_seed(
        "Why did Example Room Light 3 turn on?",
        [_identity("Example Room Light 2", "2")],
    ) is None


def test_explicit_unique_minute_and_calendar_day_select_short_event():
    evidence = _base_history()
    assert has_explicit_focal_clock(QUESTION)
    selected = explicitly_focused_event_rows(evidence, QUESTION)
    assert len(selected) == 1
    assert selected[0]["start"].startswith("2026-10-12T08:16:10")
    assert selected[0]["durationSeconds"] == 133


def test_ambiguous_minute_and_explicit_wrong_date_fail_closed():
    events = _base_history()
    events[0]["details"]["temporalAnalysis"]["observedIntervals"].append({
        "start": "2026-10-12T08:16:48.000+0100",
        "end": "2026-10-12T08:19:00.000+0100",
        "durationSeconds": 132,
    })
    assert not explicitly_focused_event_rows(events, QUESTION)
    assert not explicitly_focused_event_rows(_base_history(), (
        "Why did Example Room Light turn on at 08:16 on 11 October?"
    ))
    precise = (
        "Why did Example Room Light turn on at 08:16:10 on 12 October?"
    )
    assert len(explicitly_focused_event_rows(events, precise)) == 1


def test_explicit_short_event_gets_log_window_before_older_long_intervals():
    evidence = _base_history()
    windows = causal_boundary_log_windows(
        evidence, original_user=QUESTION, max_intervals=1
    )
    assert len(windows) == 2
    assert windows[0]["subjectBoundary"].startswith("2026-10-12T08:16:10")
    assert windows[0]["since"].startswith("2026-10-12T07:16:00")
    assert windows[1]["boundaryRole"] == "end"
    assert windows[1]["subjectBoundary"].startswith("2026-10-12T08:18:23")


def test_physical_graph_separates_bridge_report_button_reaction_and_inactive_sensor():
    graph = build_causal_evidence_graph(_physical_evidence(), QUESTION)
    assert graph["scope"] == "single-observed-event"
    assert graph["focus"]["durationSeconds"] == 133
    assert graph["directCommand"] is None
    assert graph["physicalStateBoundary"]["reporter"]["label"] == "Matter Hue Bridge Pro"
    assert graph["physicalStateBoundary"]["eventType"] == "physical"
    assert graph["physicalStateBoundary"]["listenersNotified"][0]["appId"] == "4015"
    assert graph["controllerCandidate"]["label"] == "Example Hue dimmer 1"
    assert graph["controllerCandidate"]["signedDeltaMs"] == 82.0
    assert graph["controllerCandidate"]["recordedOrder"] == "controller-event-after-light-state"
    assert graph["controllerCandidate"]["repeatedAlignedStarts"] == 3
    assert graph["controllerCandidate"]["directControllerToDeviceMappingProven"] is False
    assert graph["postOnCommands"][0]["command"] == "Command called: setLevel(45)"
    assert graph["postOnCommands"][0]["afterOnMs"] == 51.0
    assert graph["postOnCommands"][0]["notTheOriginalOnCommand"]
    assert graph["reactiveApp"]["appId"] == "4015"
    assert graph["reactiveApp"]["wasNotified"] is True
    assert graph["reactiveApp"]["configuration"]["checked"] is True
    assert graph["reactiveApp"]["executionLogs"]["result"] == "zero-observed-entries"
    assert graph["offSensorCorrelations"][0]["signedDeltaMs"] == -210.0
    assert not graph["offSensorCorrelations"][0]["offCommandProducerEstablished"]
    assert graph["offAttribution"] == "unresolved-no-proven-off-command"
    assert graph["locationMode"]["lastObservedBeforeEvent"]["value"] == "School Run"
    assert graph["physicalEvidenceComplete"]
    assert supports_one_pass_deep_synthesis(graph, QUESTION)


def test_physical_source_gaps_continue_tool_investigation():
    for params in (
        {"include_post": False},
        {"app_config": False},
    ):
        graph = build_causal_evidence_graph(_physical_evidence(**params), QUESTION)
        assert not graph["physicalEvidenceComplete"]
        assert not supports_one_pass_deep_synthesis(graph, QUESTION)
    graph = build_causal_evidence_graph(_physical_evidence(include_mode=False), QUESTION)
    assert graph["physicalEvidenceComplete"]
    assert needs_mode_history(graph, QUESTION)
    assert not supports_one_pass_deep_synthesis(graph, QUESTION)


def test_app_direct_command_path_retains_existing_contract():
    from test_causal_evidence_graph_0_17_11 import _receipts, QUESTION as old_question

    graph = build_causal_evidence_graph(_receipts(), old_question)
    assert graph["directCommand"]["producer"]["id"] == "4013"
    assert graph["physicalEvidenceComplete"] is False
    assert graph["ready"]
    assert supports_one_pass_deep_synthesis(graph, old_question)
