"""0.17.35 manual-OFF lockout: demand timed events, not live health snapshots.

No real hub connections, device writes or automation changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from motion_lockout_investigation import (
    _candidate_devices, is_motion_lockout_investigation, last_observed_off,
    prefetch_motion_lockout, resolve_named_light,
)


QUESTION = (
    "Investigate the latest manual OFF followed by motion for Livingroom "
    "Light 1. Determine whether app 4019's three-minute motion lockout "
    "engaged, separating physical button events, motion events and automation "
    "decisions. Read-only."
)


@pytest.mark.parametrize("question", [
    QUESTION,
    "Why did Livingroom Light 1 turn back on after a manual off despite its motion lockout?",
    "Trace a physical switch off, motion and whether a three-minute inhibition engaged.",
])
def test_historical_lockout_questions_match(question):
    assert is_motion_lockout_investigation(question)


@pytest.mark.parametrize("question", [
    "Show current motion lockout configuration in Livingroom Light 1",
    "Which light sensors have motion active right now?",
    "Run the comprehensive hub system audit",
    "Turn Livingroom Light 1 off",
])
def test_non_temporal_questions_remain_outside_lockout_preflight(question):
    assert not is_motion_lockout_investigation(question)


def identities():
    return [
        {"id": "1001", "label": "Livingroom Light 1", "room": "Livingroom",
         "capabilities": ["Switch"], "attributes": {"switch": "off"}},
        {"id": "1002", "label": "Livingroom Light 2", "room": "Livingroom",
         "capabilities": ["Switch"], "attributes": {"switch": "off"}},
        {"id": "7764", "label": "FP300 Livingroom sensor", "room": "Livingroom",
         "capabilities": ["MotionSensor"], "attributes": {"motion": "active"}},
        {"id": "7778", "label": "Linptech Kitchen sensor", "room": "Kitchen",
         "capabilities": ["MotionSensor"], "attributes": {"motion": "inactive"}},
        {"id": "1222", "label": "Livingroom dimmer - 1",
         "room": "Button Controllers", "capabilities": ["PushableButton"],
         "attributes": {"pushed": "1"}},
        {"id": "1888", "label": "Bedroom 1 dimmer - 1",
         "room": "Button Controllers", "capabilities": ["PushableButton"],
         "attributes": {"pushed": "1"}},
    ]


def test_named_light_resolution_and_relevant_cross_room_sensor_discovery():
    target = resolve_named_light(QUESTION, identities())
    assert target["id"] == "1001"
    sensors, buttons = _candidate_devices(
        identities(), target,
        "FP300 Livingroom sensor, Linptech Kitchen sensor, "
        "Livingroom dimmer - 1",
    )
    assert {str(x["id"]) for x in sensors} == {"7764", "7778"}
    assert [str(x["id"]) for x in buttons] == ["1222"]
    assert resolve_named_light(
        "Investigate lockout on an unspecified light", identities()
    ) is None


def test_last_off_uses_latest_closed_transition_without_claiming_manual_source():
    t = datetime.now(timezone.utc)
    hist = {"temporalAnalysis": {"observedIntervals": [
        {"end": (t - timedelta(hours=4)).isoformat()},
        {"end": (t - timedelta(minutes=12)).isoformat()},
    ]}}
    assert last_observed_off(hist) == t - timedelta(minutes=12)
    assert last_observed_off({"temporalAnalysis": {"observedIntervals": [
        {"end": t.isoformat(), "clippedAtWindowEnd": True}
    ]}}) is None


class FakeMcp:
    async def get_device_identities(self):
        return identities()

    def __init__(self):
        self.calls = []

    async def call_tool(self, gateway, request):
        self.calls.append((gateway, request))
        leaf = request["tool"]
        if leaf == "hub_get_app_config":
            return SimpleNamespace(data={"page": {"sections": [{
                "title": "Motion",
                "paragraphs": [
                    "motion FP300 Livingroom sensor Linptech Kitchen sensor"
                ],
            }]}})
        if leaf == "hub_get_logs":
            return SimpleNamespace(data={"logs": []})
        raise AssertionError("Unexpected Hubitat request " + leaf)


class FakeExecutor:
    def __init__(self, off):
        self.off = off
        self.calls = []

    async def execute(self, name, args, **kwargs):
        self.calls.append((name, args))
        assert name == "homebrain_device_history"
        return SimpleNamespace(
            success=True, result=SimpleNamespace(data={
                "temporalAnalysis": {"observedIntervals": [{
                    "start": (self.off-timedelta(minutes=7)).isoformat(),
                    "end": self.off.isoformat(),
                }]},
                "correlationEvents": [
                    {"value": "off", "date": self.off.isoformat()}
                ],
            }),
        )


class FakeJournal:
    enabled = True
    _started = True

    def __init__(self, off):
        self.off = off
        self.calls = []

    def query(self, *, since, until, device_id, attribute, limit):
        self.calls.append((device_id, attribute, since, until))
        changes = {
            ("1001", "switch"): ("off", self.off),
            ("7764", "motion"): ("active", self.off+timedelta(seconds=45)),
            ("7778", "motion"): ("inactive", self.off+timedelta(seconds=47)),
            ("1222", "pushed"): ("1", self.off+timedelta(milliseconds=450)),
        }
        value, stamp = changes.get((device_id, attribute), ("", self.off))
        events = [] if not value else [{
            "stream": "events", "value": value, "attribute": attribute,
            "observed_at": stamp.isoformat(),
            "timestamp_basis": "collector-received",
        }]
        return {"events": events, "count": len(events),
                "gaps": [], "coverage_complete": False}


class Evidence:
    def __init__(self):
        self.records = []

    def record(self, *args, **kwargs):
        self.records.append((args, kwargs))


class Catalog:
    def declared_tool(self, name):
        return object() if name == "homebrain_device_history" else None


@pytest.mark.asyncio
async def test_historical_lockout_collects_event_sequence_not_health():
    off = datetime.now(timezone.utc) - timedelta(minutes=12)
    mcp, exe, journal, evidence = (
        FakeMcp(), FakeExecutor(off), FakeJournal(off), Evidence()
    )
    host = SimpleNamespace(
        mcp=mcp, executor=exe, historical_journal=journal,
        evidence=evidence, _tool_succeeded=lambda result: True,
    )
    messages = []
    ok = await prefetch_motion_lockout(
        host, QUESTION, catalog=Catalog(), messages=messages,
    )
    assert ok
    assert [name for name, _ in exe.calls] == [
        "homebrain_device_history", "homebrain_device_history",
    ]
    assert {request["tool"] for _, request in mcp.calls} == {
        "hub_get_app_config", "hub_get_logs",
    }
    assert {i[:2] for i in journal.calls} == {
        ("1001", "switch"), ("7764", "motion"),
        ("7778", "motion"), ("1222", "pushed"),
    }
    info = evidence.records[-1][1]["details"]
    assert info["appId"] == "4019"
    assert info["subject"] == "Livingroom Light 1"
    assert info["focalOff"] == off.isoformat()
    assert info["status"] == "partial-focal-sequence"
    assert info["window"]["threeMinuteWindowElapsed"] is True
    assert info["nearbyButtonEvents"][0]["timestampBasis"] == "collector-received"
    assert info["manualOffVerified"] is False
    assert info["lockoutExecutionVerified"] is False
    assert info["lockoutFailureVerified"] is False
    assert info["coverageComplete"] is False
    assert all("hub_get_device" != x["tool"] for _, x in mcp.calls)
    assert "configuration alone" not in str(info).lower()
    assert any("HOST LOCKOUT HISTORICAL EVIDENCE" in row["content"]
               for row in messages)


@pytest.mark.asyncio
async def test_missing_light_history_is_reported_as_incomplete_not_as_no_lockout():
    host = SimpleNamespace(
        mcp=FakeMcp(), executor=FakeExecutor(datetime.now(timezone.utc)),
        historical_journal=None,
        evidence=Evidence(), _tool_succeeded=lambda result: True,
    )
    # No matching light in the request: do not guess a device or query
    # generic whole-hub history, and never invent an executed lockout.
    vague = ("Investigate why manual OFF and motion lockout on a light "
             "did not engage app 4019. Read-only.")
    assert is_motion_lockout_investigation(vague)
    messages = []
    assert await prefetch_motion_lockout(
        host, vague, catalog=Catalog(), messages=messages,
    )
    assert host.evidence.records[-1][1]["details"]["status"] == "no-focal-off-observed"
    assert host.evidence.records[-1][1]["details"]["lockoutExecutionVerified"] is False
