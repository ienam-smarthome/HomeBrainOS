"""0.17.48: an explicitly named historical event must determine read bounds.

The 12 Oct 23:49:27 BST event fell 24h 3m before the 13 Oct 22:52 UTC
live test. The previous fixed 24-hour light/button/native-command read
silently excluded evidence previously returned in an earlier investigation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from focal_history_lookback import explicit_focal_history_lookback
from focal_history_report import render_bounded_focal_reconstruction
from motion_lockout_investigation import prefetch_motion_lockout


QUERY = (
    "Independently reconstruct Livingroom Light 1's OFF at approximately "
    "23:49:27 BST on 12 October 2026. Correlate device 746's native physical "
    "button press, app 1251's OFF command, native device 7805 state history, "
    "Historical Journal OFF observations, subsequent motion, and app 4019's "
    "lockout decision. Distinguish native event timestamps from collector-received "
    "timestamps and explain any missing evidence. Read-only."
)
NOW = datetime(2026, 10, 13, 22, 52, 28, tzinfo=timezone.utc)


def test_24_hour_default_misses_focal_and_expands_to_26_hours():
    r = explicit_focal_history_lookback(QUERY, now=NOW)
    assert r["requestedEventUtc"] == "2026-10-12T22:49:27+00:00"
    assert r["hoursBackRequested"] == 26
    assert r["defaultWindowWouldMissFocal"] is True
    assert r["expandedBeyondDefault"] is True
    assert r["requestedBeyondMaxLookback"] is False
    assert r["successfulRequestNotProofOfSourceRetention"] is True


def test_within_default_window_avoids_unnecessary_expansion():
    r = explicit_focal_history_lookback(
        QUERY, now=datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc),
    )
    assert r["hoursBackRequested"] == 24
    assert r["defaultWindowWouldMissFocal"] is False


def test_beyond_seven_days_fails_closed_on_coverage():
    r = explicit_focal_history_lookback(
        QUERY, now=datetime(2026, 10, 21, 22, 0, tzinfo=timezone.utc),
    )
    assert r["hoursBackRequested"] == 168
    assert r["requestedBeyondMaxLookback"] is True


def test_invalid_or_unlabelled_clock_does_not_become_utc():
    unlabelled = QUERY.replace("23:49:27 BST", "23:49:27")
    assert explicit_focal_history_lookback(
        unlabelled, now=NOW,
    )["status"] == "no-trusted-explicit-anchor"
    wrong_zone = QUERY.replace("23:49:27 BST", "23:49:27 GMT")
    assert explicit_focal_history_lookback(
        wrong_zone, now=NOW,
    )["hoursBackRequested"] == 24


def _host(recover_native: bool):
    light = {
        "id": "7805", "label": "Livingroom Light 1",
        "name": "Livingroom Light 1", "room": "Living Room",
        "attributes": {"switch": "off"},
    }
    button = {
        "id": "746", "label": "🔢 Living Room Button",
        "name": "🔢 Living Room Button", "room": "Button Controllers",
        "attributes": {"pushed": "1"}, "capabilities": ["PushableButton"],
    }
    desk = {
        "id": "7981", "label": "FP400 Computer Desk",
        "name": "FP400 Computer Desk", "room": "Living Room",
        "attributes": {"motion": "inactive"}, "capabilities": ["MotionSensor"],
    }
    calls, receipts = [], []

    class MCP:
        async def get_device_identities(self):
            return [light, button, desk]

    class Executor:
        async def execute(self, name, args, **kwargs):
            calls.append((name, args))
            if name == "homebrain_device_history":
                hours = args.get("hours_back", 24)
                if args["attribute"] == "pushed":
                    data = {"observedEvents": [
                        {"name": "pushed", "value": "1", "type": "physical",
                         "date": "2026-10-12T23:49:27.303+0100",
                         "producedBy": {"id": "746", "type": "device"}},
                    ]} if hours >= 26 and recover_native else {"observedEvents": []}
                else:
                    data = {
                        "temporalAnalysis": {"observedIntervals": [
                            {"start": "2026-10-13T21:34:00+0100",
                             "end": "2026-10-13T21:35:00+0100"},
                        ]},
                        "commandEvents": (
                            [{"name": "command-off",
                              "date": "2026-10-12T23:49:27.336+0100",
                              "producedBy": {
                                  "id": "1251", "type": "app",
                                  "label": "button 1 pushed",
                              }}] if hours >= 26 and recover_native else []
                        ),
                    }
            elif args.get("tool") == "hub_get_app_config":
                data = {"settings": {"motionOffLockoutMinutes": "300"}}
            elif args.get("tool") == "hub_get_logs":
                assert args["args"]["appId"] == "4019"
                assert args["args"]["since"].startswith("2026-10-12T22:49:07")
                data = {"logs": []}
            else:
                raise AssertionError((name, args))
            return SimpleNamespace(
                success=True, result=SimpleNamespace(data=data),
            )

    class Archive:
        enabled = True
        _started = True

        def query(self, *, device_id, attribute, **kwargs):
            if device_id == "7805":
                events = [
                    ("switch", "off", "2026-10-12T22:49:28.622842+00:00"),
                ]
            elif device_id == "746":
                events = [
                    ("pushed", "1", "2026-10-12T22:49:28.397663+00:00"),
                ]
            elif device_id == "7981":
                events = [
                    ("motion", "active", "2026-10-12T22:49:33.826378+00:00"),
                ]
            else:
                events = []
            rows = [
                {"stream": "events", "attribute": a, "value": v,
                 "observed_at": at, "timestamp_basis": "collector-received"}
                for a,v,at in events
            ]
            return {"events": rows, "count": len(rows), "gaps": [
                {"reason": "collector disconnected"},
            ]}

    class Evidence:
        def record(self, name, args, **kwargs):
            receipts.append({
                "tool": name, "success": kwargs.get("success"),
                "details": kwargs.get("details"),
            })

    class Catalog:
        def declared_tool(self, name):
            return object()

    host = SimpleNamespace(
        mcp=MCP(), executor=Executor(), evidence=Evidence(),
        historical_journal=Archive(),
    )
    return host, Catalog(), calls, receipts


@pytest.mark.asyncio
async def test_one_bounded_expanded_read_recovers_native_command_and_button():
    host, catalog, calls, receipts = _host(True)
    messages = []
    assert await prefetch_motion_lockout(
        host, QUERY, catalog=catalog, messages=messages,
    )
    history = [a for name,a in calls if name == "homebrain_device_history"]
    assert len(history) == 2
    assert history[0]["hours_back"] >= 26
    assert history[1]["hours_back"] >= 26
    facts = next(x["details"] for x in receipts
                 if x["tool"] == "homebrain_motion_lockout_investigation")
    assert facts["nativeHistoryLookback"]["hoursBackRequested"] >= 26
    assert facts["nativeFocalCommandRowsRetained"] == 1
    assert facts["nativeFocalCommandProducers"][0]["producerAppId"] == "1251"
    assert facts["crossSourceFocalProvenance"]["nativeButtonCommandVerified"]
    assert facts["crossSourceFocalProvenance"]["journalLightOffObserved"]
    assert facts["manualOffVerified"] is False  # no native switch OFF row
    report = render_bounded_focal_reconstruction(QUERY, receipts)
    assert report is not None
    assert "Native OFF command" in report
    assert "app 1251" in report
    assert "device 746" in report
    assert "collector-received" in report
    assert "FP400 Computer Desk" in report
    assert "activation eligibility **not verified**" in report
    assert "Historical decision" in report or "timer start" in report
    assert "not" in report.casefold()


@pytest.mark.asyncio
async def test_extended_history_still_empty_reports_retention_limit_not_nonexecution():
    host, catalog, calls, receipts = _host(False)
    assert await prefetch_motion_lockout(
        host, QUERY, catalog=catalog, messages=[],
    )
    report = render_bounded_focal_reconstruction(QUERY, receipts)
    assert report is not None
    assert "No matching native OFF command appears" in report
    assert "does not prove no OFF command occurred" in report
    assert "No native light OFF state transition" in report
    assert "Light OFF observed at" in report
    assert "Journal controller" in report
    assert "No Hubitat configuration or device was changed" in report
    assert "2 recorded journal gap" not in report  # one counted gap, not invented two
    assert "1 recorded journal gap" in report


def test_report_does_not_skip_missing_source_class():
    _, _, _, receipts = _host(False)
    assert render_bounded_focal_reconstruction(QUERY, receipts) is None
    bad = [{
        "tool": "homebrain_motion_lockout_investigation", "success": True,
        "details": {
            "appId": "4019", "lightDeviceId": "7805",
            "focalSelection": {"explicitTargetUtc": "2026-10-12T22:49:27+00:00"},
            "sources": [{"source": "bounded-light-device-history", "success": True}],
        },
    }]
    assert render_bounded_focal_reconstruction(QUERY, bad) is None
    assert render_bounded_focal_reconstruction(
        QUERY + " Also investigate hub performance", bad,
    ) is None
