"""0.17.47: correlate native control events with archived observations.

Live case: 12 Oct 2026 23:49:27 BST. Native switch-state newest-N results
contain no 12 Oct OFF, but native command and button feeds retain independent
rows. Historical Journal has collector-received OFF and later FP400 motion.
This is source corroboration, NOT proof of native light-state clock or
automation lockout activation.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from focal_event_cross_source import correlate_requested_focal_sources
from motion_lockout_investigation import (
    collected_explicit_focal_ready_for_synthesis, prefetch_motion_lockout,
)


PROMPT = (
    "Independently reconstruct Livingroom Light 1's OFF at approximately "
    "23:49:27 BST on 12 October 2026. Correlate device 746's physical button "
    "press, app 1251's OFF command, device 7805's state, subsequent eligible "
    "motion and app 4019's lockout decision. Use correct UTC log windows. Read-only."
)
ANCHOR = "2026-10-12T22:49:27+00:00"


def native_light():
    return {
        "temporalAnalysis": {"observedIntervals": [
            {"start": "2026-10-13T22:49:18+0100",
             "end": "2026-10-13T22:52:21.258+0100"},
        ]},
        "commandEvents": [
            {"name": "command-off",
             "date": "2026-10-12T23:49:27.336+0100",
             "producedBy": {"label": "button 1 pushed",
                            "id": "1251", "type": "app"}},
            {"name": "command-off",
             "date": "2026-10-12T23:49:11.898+0100",
             "producedBy": {"label": "button 1 pushed",
                            "id": "1251", "type": "app"}},
        ],
    }


def presses():
    return [
        {"deviceId": "746", "buttonNumber": "1",
         "occurredAt": "2026-10-12T22:49:27.303+00:00",
         "source": "native physical button event"},
        {"deviceId": "746", "buttonNumber": "2",
         "occurredAt": "2026-10-12T22:49:28.477+00:00",
         "source": "native physical button event"},
    ]


def journal():
    return [
        {"kind": "light", "deviceId": "7805",
         "observations": [
             {"value": "off",
              "observedAt": "2026-10-12T22:49:28.622842+00:00",
              "timestampBasis": "collector-received"},
         ]},
        {"kind": "sensor", "deviceId": "7981",
         "label": "FP400 Computer Desk",
         "activationSourceVerified": False,
         "activationRole": "unverified-from-current-configuration",
         "observations": [
             {"value": "active",
              "observedAt": "2026-10-12T22:49:33.826378+00:00",
              "timestampBasis": "collector-received"},
         ]},
    ]


def test_native_button_command_and_journal_off_are_distinct_sources():
    r = correlate_requested_focal_sources(
        native_light(), presses(), journal(),
        anchor_utc=ANCHOR, light_device_id="7805",
    )
    assert r["nativeButtonCommandVerified"] is True
    assert r["nativeLightStateObserved"] is False
    assert r["journalLightOffObserved"] is True
    assert r["lockoutExecutionVerified"] is False
    c = r["candidate"]
    assert c["nativePhysicalPressAtUtc"] == "2026-10-12T22:49:27.303+00:00"
    assert c["nativeOffCommandAtUtc"] == "2026-10-12T22:49:27.336+00:00"
    assert c["commandProducerAppId"] == "1251"
    assert c["physicalButtonDeviceId"] == "746"
    assert c["physicalButtonNumber"] == "1"
    assert c["buttonToCommandMilliseconds"] == 33
    assert c["evidenceLevel"] == "native-physical-command-plus-journal-observation"
    assert c["journalLightOff"]["timestampBasis"] == "collector-received"
    assert c["journalLightOff"]["originalDeviceEventClockKnown"] is False
    assert c["journalLightOff"]["millisecondsAfterNativeCommand"] > 1000
    assert c["lockoutEffectEstablished"] is False


def test_wrong_button_number_does_not_prove_app_command_chain():
    wrong_press = [dict(presses()[0], buttonNumber="2")]
    r = correlate_requested_focal_sources(
        native_light(), wrong_press, journal(),
        anchor_utc=ANCHOR, light_device_id="7805",
    )
    assert r["candidate"] is None
    assert r["nativeButtonCommandVerified"] is False


def test_missing_collector_state_does_not_create_switch_transition():
    r = correlate_requested_focal_sources(
        native_light(), presses(), [],
        anchor_utc=ANCHOR, light_device_id="7805",
    )
    assert r["nativeButtonCommandVerified"] is True
    assert r["nativeLightStateObserved"] is False
    assert r["journalLightOffObserved"] is False
    assert r["candidate"]["evidenceLevel"] == "native-physical-and-command-only"


def test_journal_wrong_device_or_timestamp_cannot_be_reused():
    wrong = [dict(journal()[0], deviceId="9999")]
    r = correlate_requested_focal_sources(
        native_light(), presses(), wrong,
        anchor_utc=ANCHOR, light_device_id="7805",
    )
    assert r["journalLightOffObserved"] is False
    wrong_timestamp = [
        dict(journal()[0], observations=[
            dict(journal()[0]["observations"][0],
                 observedAt="2026-10-12T22:49:40+00:00")
        ]),
    ]
    r = correlate_requested_focal_sources(
        native_light(), presses(), wrong_timestamp,
        anchor_utc=ANCHOR, light_device_id="7805",
    )
    assert r["journalLightOffObserved"] is False


def test_journal_not_a_native_source_when_time_fields_are_unknown():
    wrong = [dict(journal()[0], observations=[
        dict(journal()[0]["observations"][0],
             timestampBasis="device-emitted")
    ])]
    r = correlate_requested_focal_sources(
        native_light(), presses(), wrong,
        anchor_utc=ANCHOR, light_device_id="7805",
    )
    assert r["journalLightOffObserved"] is False


def test_real_native_state_is_independent_of_journal():
    light = native_light()
    light["temporalAnalysis"]["observedIntervals"].append({
        "start": "2026-10-12T23:49:18+0100",
        "end": "2026-10-12T23:49:27.529+0100",
    })
    r = correlate_requested_focal_sources(
        light, presses(), [],
        anchor_utc=ANCHOR, light_device_id="7805",
    )
    assert r["nativeLightStateObserved"] is True
    assert r["journalLightOffObserved"] is False
    assert r["candidate"]["evidenceLevel"] == "native-physical-command-state"


@pytest.mark.asyncio
async def test_prefetch_preserves_separate_clock_and_eligibility():
    light = {"id": "7805", "name": "Livingroom Light 1",
             "label": "Livingroom Light 1", "room": "Living Room",
             "attributes": {"switch": "off"}}
    button = {"id": "746", "name": "🔢 Living Room Button",
              "label": "🔢 Living Room Button",
              "room": "Button Controllers",
              "attributes": {"pushed": "1"}, "capabilities": ["PushableButton"]}
    records, calls = [], []

    class MCP:
        async def get_device_identities(self):
            return [light, button]

    class Exec:
        async def execute(self, name, args, **kwargs):
            calls.append((name, args))
            if name == "homebrain_device_history":
                if args["attribute"] == "pushed":
                    data = {"observedEvents": [
                        {"name": "pushed", "value": "1", "type": "physical",
                         "date": "2026-10-12T23:49:27.303+0100",
                         "producedBy": {"id": "746", "type": "device"}},
                    ]}
                else:
                    data = native_light()
            elif args.get("tool") == "hub_get_app_config":
                data = {"settings": {"motionOffLockoutMinutes": "300"}}
            elif args.get("tool") == "hub_get_logs":
                data = {"logs": []}
            else:
                raise AssertionError((name, args))
            return SimpleNamespace(success=True, result=SimpleNamespace(data=data))

    class Journal:
        enabled = True
        _started = True

        def query(self, *, device_id, attribute, **kwargs):
            matches = [
                item for item in journal()
                if item.get("deviceId") == str(device_id)
            ]
            observations = [
                {"stream": "events", "value": obs["value"],
                 "attribute": attribute, "observed_at": obs["observedAt"],
                 "timestamp_basis": obs["timestampBasis"]}
                for row in matches for obs in row["observations"]
            ]
            return {"count": len(observations), "events": observations, "gaps": []}

    class Evidence:
        def record(self, name, args, **kwargs):
            records.append({"tool": name, "success": kwargs.get("success"),
                            "details": kwargs.get("details")})

    class Catalog:
        def declared_tool(self, name):
            return object()

    host = SimpleNamespace(
        mcp=MCP(), executor=Exec(),
        evidence=Evidence(), historical_journal=Journal(),
    )
    messages = []
    assert await prefetch_motion_lockout(
        host, PROMPT, catalog=Catalog(), messages=messages,
    )
    facts = next(x["details"] for x in records
                 if x["tool"] == "homebrain_motion_lockout_investigation")
    fused = facts["crossSourceFocalProvenance"]
    assert facts["status"] == "explicit-event-not-observed"
    assert facts["requestedEventStateObserved"] is False
    assert facts["manualOffVerified"] is False
    assert fused["nativeButtonCommandVerified"] is True
    assert fused["nativeLightStateObserved"] is False
    assert fused["journalLightOffObserved"] is True
    assert fused["candidate"]["commandProducerAppId"] == "1251"
    assert facts["motionCorrelationAnchor"].startswith("collector-received")
    assert any(
        x["deviceId"] == "7981" and x["timestampBasis"] == "collector-received"
        and x["eligibleActivationSourceVerified"] is False
        for x in facts["motionCorrelations"]
    )
    assert collected_explicit_focal_ready_for_synthesis(
        PROMPT, records,
    ) is True
    assert all(
        x["args"]["since"].startswith("2026-10-12T22:49:07")
        for name,x in calls if x.get("tool") == "hub_get_logs"
    )


def test_explicit_gate_does_not_fire_when_missing_journal_or_button():
    base = {
        "status": "explicit-event-not-observed",
        "focalSelection": {"explicitTargetUtc": ANCHOR, "selectedOff": None},
        "crossSourceFocalProvenance": {
            "requestedEventUtc": ANCHOR, "nativeButtonCommandVerified": True,
            "journalLightOffObserved": True, "nativeLightStateObserved": False,
        },
        "currentConfiguration": {"settingsRead": True},
        "sources": [
            {"source": "bounded-light-device-history", "success": True},
            {"source": "targeted-native-controller-history", "readSucceeded": True},
            {"source": "bounded-app-execution-logs", "readSucceeded": True},
            {"source": "Historical Journal", "deviceScopesChecked": 2},
        ],
    }
    rows = [{"tool": "homebrain_motion_lockout_investigation", "success": True,
             "details": base}]
    assert collected_explicit_focal_ready_for_synthesis(PROMPT, rows)
    import copy
    for key in ("nativeButtonCommandVerified", "journalLightOffObserved"):
        modified = copy.deepcopy(rows)
        modified[0]["details"]["crossSourceFocalProvenance"][key] = False
        assert not collected_explicit_focal_ready_for_synthesis(PROMPT, modified)
    modified = copy.deepcopy(rows)
    modified[0]["details"]["sources"][-1]["deviceScopesChecked"] = 0
    assert not collected_explicit_focal_ready_for_synthesis(PROMPT, modified)
