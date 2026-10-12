"""0.17.40: native temporal intervals and command provenance regression.

The temporal source names intervals under temporalAnalysis.intervals, while the
technical receipt calls them observedIntervals. Before this release prefetch
used only the receipt name, so it incorrectly reported no focal OFF.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

from motion_lockout_investigation import (
    completed_light_intervals, last_observed_off,
    focal_command_provenance, prefetch_motion_lockout,
)


def _native_history():
    return {
        "label": "Livingroom Light 1",
        "temporalAnalysis": {"intervals": [
            {"start": "2026-10-12T17:44:13.454+0100",
             "end": "2026-10-12T23:49:12.284+0100",
             "clippedAtWindowEnd": False},
            {"start": "2026-10-12T23:49:19.140+0100",
             "end": "2026-10-12T23:49:27.529+0100",
             "clippedAtWindowEnd": False},
        ]},
        "commandEvents": [
            {"name": "command-off", "date": "2026-10-12T23:49:27.336+0100",
             "producedBy": {"id": "1251", "type": "app",
                            "label": "button 1 pushed"}},
            {"name": "command-on", "date": "2026-10-12T23:49:18.988+0100",
             "producedBy": {"id": "1251", "type": "app",
                            "label": "button 1 pushed"}},
            {"name": "command-off", "date": "2026-10-12T23:49:11.898+0100",
             "producedBy": {"id": "1251", "type": "app",
                            "label": "button 1 pushed"}},
        ],
    }


def test_native_and_receipt_shapes_identify_same_latest_off():
    native = _native_history()
    receipt = {"temporalAnalysis": {
        "observedIntervals": native["temporalAnalysis"]["intervals"]}}
    expected = datetime.fromisoformat("2026-10-12T22:49:27.529+00:00")
    assert len(completed_light_intervals(native)) == 2
    assert len(completed_light_intervals(receipt)) == 2
    assert last_observed_off(native) == expected
    assert last_observed_off(receipt) == expected


def test_exact_command_source_precedes_off_not_independent_button_proof():
    native = _native_history()
    matches = focal_command_provenance(native, off=last_observed_off(native))
    assert len(matches) == 1
    assert matches[0]["producer"] == {
        "id": "1251", "type": "app", "label": "button 1 pushed"}
    assert matches[0]["commandPrecedesStateMs"] == 193.0
    assert matches[0]["commandProducerVerified"] is True
    assert matches[0]["hardwareButtonPressVerified"] is False
    assert matches[0]["lockoutExecutionVerified"] is False


def test_absent_intervals_or_out_of_window_commands_do_not_invent_proof():
    native = {"temporalAnalysis": {"intervals": []},
              "commandEvents": [
                  {"name": "command-off",
                   "date": "2026-10-11T23:49:27.336+0100",
                   "producedBy": {"id": "1251", "type": "app"}},
              ]}
    assert last_observed_off(native) is None
    at = datetime.fromisoformat("2026-10-12T23:49:27.529+0100")
    assert focal_command_provenance(native, off=at) == []


def test_prefetch_reaches_app_logs_after_native_completed_off():
    identity = {"id": "7805", "name": "Livingroom Light 1",
                "label": "Livingroom Light 1",
                "attributes": {"switch": "off"}}
    calls, records = [], []

    class MCP:
        async def get_device_identities(self):
            return [identity]

    class Executor:
        async def execute(self, name, args, **kwargs):
            calls.append((name, args))
            if name == "homebrain_device_history":
                data = _native_history()
            elif args.get("tool") == "hub_get_app_config":
                data = {"app": {"id": 4019, "name": "Livingroom Light 1"}}
            elif args.get("tool") == "hub_get_logs":
                data = {"logs": []}
            else:
                raise AssertionError(f"Unexpected tool: {name} {args!r}")
            return SimpleNamespace(
                success=True, result=SimpleNamespace(data=data))

    class Evidence:
        def record(self, name, arguments, **kwargs):
            records.append({"tool": name, "arguments": arguments, **kwargs})

    class Catalog:
        def declared_tool(self, name):
            return object() if name in (
                "homebrain_device_history", "hub_read_apps_code",
                "hub_read_diagnostics",
            ) else None

    host = SimpleNamespace(mcp=MCP(), executor=Executor(),
                           evidence=Evidence(), historical_journal=None)
    messages = []
    prompt = ("Investigate the latest manual OFF of Livingroom Light 1 "
              "followed by motion. Did app 4019's three-minute lockout engage? "
              "Read-only.")
    handled = asyncio.run(prefetch_motion_lockout(
        host, prompt, catalog=Catalog(), messages=messages))
    assert handled
    finding = next(x["details"] for x in records
                   if x["tool"] == "homebrain_motion_lockout_investigation")
    assert finding["status"] == "partial-focal-sequence"
    assert finding["sources"][0]["observedIntervals"] == 2
    assert finding["focalOff"] == "2026-10-12T22:49:27.529000+00:00"
    assert finding["focalCommandProvenance"][0]["producer"]["id"] == "1251"
    assert finding["manualOffVerified"] is False
    assert finding["lockoutExecutionVerified"] is False
    assert any(call[1].get("tool") == "hub_get_logs"
               and call[1].get("args", {}).get("appId") == "4019"
               for call in calls)
    assert "focalCommandProvenance" in messages[-1]["content"]
