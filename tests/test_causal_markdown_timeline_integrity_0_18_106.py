"""Regression for the Livingroom Light 1 causal timeline corruption.

A Hubitat physical state edge may list a rule under triggered[], which is a
listener, not proof that the rule sent the ON/OFF command. Correct its causal
attribution without deleting timestamps or corrupting the Markdown table.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(ROOT))

from causal_attribution_guard import guard_triggered_listener_causal_claim
from synthesis_validator import validate_synthesis


def hubitat_history():
    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "mutates": False,
        "effect": "read",
        "details": {
            "label": "Livingroom Light 1",
            "boundaryEvents": [
                {
                    "name": "switch", "value": "on",
                    "type": "physical", "isStateChange": True,
                    "date": "2026-10-24T18:29:35.807+01:00",
                    "producedBy": {
                        "label": "Matter Hue Bridge Pro",
                        "id": "7790", "type": "device",
                    },
                    "triggered": [{
                        "name": "Livingroom Light 1 – Night Idle OFF – TEST",
                        "appId": 4246, "handler": "allHandlerX",
                    }],
                },
            ],
        },
    }]


def test_listener_correction_preserves_all_timeline_columns():
    narrative = (
        "| Start | End | Duration | Trigger / Provenance |\n"
        "| --- | --- | ---: | --- |\n"
        "| 4:29 PM | 6:29 PM | 2h | "
        "**Rule 4246 triggered the ON transition.** |\n"
        "| 6:29 PM | 6:37 PM | 8m | "
        "Unresolved: producer not established. |"
    )
    repaired, changed = guard_triggered_listener_causal_claim(
        narrative, hubitat_history(),
    )
    assert changed
    rows = [line for line in repaired.splitlines()
            if line.startswith("|") and "PM" in line]
    assert len(rows) == 2
    assert rows[0].count("|") == 5
    assert rows[1].count("|") == 5
    assert "| 4:29 PM | 6:29 PM | 2h |" in rows[0]
    assert "only as a downstream listener" in rows[0]
    assert "Matter Hue Bridge Pro" in rows[0]
    assert "Rule 4246 triggered the ON transition" not in repaired
    assert "6:29 PM | 6:37 PM | 8m" in rows[1]


def test_prose_listener_correction_still_occurs():
    claim = (
        "The Night Idle OFF automation triggered the Livingroom Light 1 "
        "ON transition."
    )
    repaired, changed = guard_triggered_listener_causal_claim(
        claim, hubitat_history(),
    )
    assert changed
    assert "downstream listener" in repaired
    assert "Matter Hue Bridge Pro" in repaired


def test_noncausal_and_nonphysical_table_rows_are_unchanged():
    narrative = (
        "| 3:49 PM | 4:18 PM | 29m | "
        "Source was Lighting: livingroom low light. |"
    )
    repaired, changed = guard_triggered_listener_causal_claim(
        narrative, hubitat_history(),
    )
    assert not changed
    assert repaired == narrative


def test_guard_does_not_corrupt_short_or_nonstandard_tables():
    text = "| Rule 4246 triggered ON |"
    repaired, changed = guard_triggered_listener_causal_claim(
        text, hubitat_history(),
    )
    assert not changed
    assert repaired == text
