from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_command_provenance import (  # noqa: E402
    command_producer_transition_sufficient,
    correlate_command_producers,
    focal_transition_boundary,
    render_boundary_producer_summary,
    render_command_producer_summary,
)


def _switch_event(value: str, date: str) -> dict:
    return {
        "name": "switch",
        "value": value,
        "date": date,
        "description": f"Hallway Light 1 switch is {value}",
        "isStateChange": True,
        "type": "physical",
        "producedBy": {
            "label": "Matter Hue Bridge Pro",
            "id": "7790",
            "type": "device",
        },
        "triggered": [
            {
                "name": "Hallway (⚪ Lights Off)",
                "appId": 4012,
                "handler": "lightSwitchHandler",
            }
        ],
    }


def _command_event(date: str, label: str = "05. Maker API - HD+") -> dict:
    return {
        "name": "command-on",
        "value": None,
        "date": date,
        "description": "Command called: on()",
        "isStateChange": False,
        "type": "command",
        "producedBy": {
            "label": label,
            "id": "2355",
            "type": "app",
        },
    }


def _evidence(*, include_latest_command: bool = False) -> list[dict]:
    old_start = "2026-09-25T12:38:03.681+0100"
    old_end = "2026-09-25T12:38:52.982+0100"
    latest_start = "2026-09-25T13:14:40.368+0100"
    latest_end = "2026-09-25T13:15:18.916+0100"

    commands = [_command_event("2026-09-25T12:38:03.452+0100")]
    if include_latest_command:
        commands.insert(
            0,
            _command_event(
                "2026-09-25T13:14:40.139+0100",
                "Latest Maker API",
            ),
        )

    return [{
        "tool": "homebrain_device_history",
        "success": True,
        "details": {
            "label": "Hallway Light 1",
            "attribute": "switch",
            "temporalAnalysis": {
                "observedIntervals": [
                    {
                        "start": old_start,
                        "end": old_end,
                        "durationSeconds": 49,
                        "duration": "49s",
                    },
                    {
                        "start": latest_start,
                        "end": latest_end,
                        "durationSeconds": 39,
                        "duration": "39s",
                    },
                ],
                "unboundedActiveInterval": False,
                "openActiveInterval": False,
            },
            "boundaryEvents": [
                _switch_event("off", latest_end),
                _switch_event("on", latest_start),
                _switch_event("off", old_end),
                _switch_event("on", old_start),
            ],
            "observedEvents": [
                _switch_event("off", latest_end),
                _switch_event("on", latest_start),
                _switch_event("off", old_end),
                _switch_event("on", old_start),
            ],
            "commandEvents": commands,
        },
    }]


def test_older_command_cannot_hijack_newest_requested_on_transition() -> None:
    evidence = _evidence()
    correlations = correlate_command_producers(evidence)

    assert len(correlations) == 1
    assert correlations[0]["stateBoundary"].startswith(
        "2026-09-25T12:38:03.681"
    )

    focal = focal_transition_boundary(evidence, "on")
    assert focal is not None
    assert focal.startswith("2026-09-25T13:14:40.368")

    assert command_producer_transition_sufficient(
        correlations,
        "on",
        requested_boundary=focal,
    ) is False

    # The finalizer must not promote the old Maker API command as the cause of
    # the newer 13:14 transition.
    assert render_command_producer_summary(evidence, transition="on") is None

    boundary = render_boundary_producer_summary(evidence, transition="on")
    assert boundary is not None
    assert "1:14:40 PM" in boundary
    assert "Matter Hue Bridge Pro" in boundary
    assert "39 seconds" in boundary
    assert "05. Maker API - HD+" not in boundary


def test_short_latest_interval_accepts_direct_command_for_same_boundary() -> None:
    evidence = _evidence(include_latest_command=True)
    correlations = correlate_command_producers(evidence)

    # The newest 39-second interval is below the generic five-minute timeline
    # materiality threshold, but authoritative command provenance must still be
    # eligible for the exact boundary.
    latest = [
        row
        for row in correlations
        if str(row.get("stateBoundary") or "").startswith(
            "2026-09-25T13:14:40.368"
        )
    ]
    assert len(latest) == 1

    focal = focal_transition_boundary(evidence, "on")
    assert command_producer_transition_sufficient(
        correlations,
        "on",
        requested_boundary=focal,
    ) is True

    message = render_command_producer_summary(evidence, transition="on")
    assert message is not None
    assert message.startswith("**Cause:** Latest Maker API issued the ON command")
    assert "1:14:40 PM" in message
    assert "229 ms later" in message
    assert "**Run:** The observed ON run lasted 39 seconds." in message
    assert "05. Maker API - HD+" not in message
