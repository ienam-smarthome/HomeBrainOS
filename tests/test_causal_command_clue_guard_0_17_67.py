"""Regression: Hue bridge reporting must not erase preceding Hubitat command."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"))
from causal_command_clue_guard import guard_causal_exclusion_with_command_clue


def _evidence():
    return [
        {
            "tool": "homebrain_device_history", "success": True,
            "details": {
                "label": "Livingroom Light 1", "attribute": "switch",
                "temporalAnalysis": {"observedIntervals": [{
                    "start": "2026-10-14T19:55:00.049+0100",
                    "end": "2026-10-14T22:45:40.112+0100",
                    "durationSeconds": 10240,
                }]},
            },
        },
        {
            "success": True, "tool": "hub_read_devices",
            "sub_tool": "hub_list_device_events",
            "arguments": {"args": {"attribute": "command-on", "deviceId": "7805"}},
            "details": {"label": "Livingroom Light 1", "eventName": "command-on", "events": [{
                "name": "command-on", "date": "2026-10-14T19:54:46.691+0100",
                "type": "command", "description": "Command called: on()",
                "producedBy": {"label": "SenseCap D1 Settings", "id": "4129", "type": "app"},
            }]},
        },
    ]


QUESTION = "Why did Livingroom Light 1 turn ON at 19:55 on 14 October 2026?"


def test_external_origin_not_proven_by_bridge():
    bad = ("The trigger originated from a controller outside the Hubitat ecosystem. "
           "No Hubitat-native rule, button, or sensor triggered the event.")
    updated, changed = guard_causal_exclusion_with_command_clue(bad, _evidence(), QUESTION)
    assert changed
    assert "originated from a controller outside" not in updated
    assert "No Hubitat-native" not in updated
    assert "SenseCap D1 Settings" in updated
    assert "13.358" in updated
    assert "unverified" in updated


def test_different_focal_event_cannot_use_stale_clue():
    updated, changed = guard_causal_exclusion_with_command_clue(
        "The trigger originated from a controller outside the Hubitat ecosystem.",
        _evidence(), "Why did Livingroom Light 1 turn ON at 20:15 on 14 October 2026?",
    )
    assert not changed


def test_no_internal_clue_no_rewrite():
    updated, changed = guard_causal_exclusion_with_command_clue(
        "The trigger originated from a controller outside the Hubitat ecosystem.",
        _evidence()[:1], QUESTION,
    )
    assert not changed
