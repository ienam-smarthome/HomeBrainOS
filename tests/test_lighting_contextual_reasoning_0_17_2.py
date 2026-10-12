"""Regression: proven custom lighting apps still require causal context."""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from causal_lighting_context import (  # noqa: E402
    choose_occupancy_event_sources,
    render_level_command_pattern,
    render_occupancy_edge_correlation,
)
from causal_rule_decision_context import proven_lighting_command  # noqa: E402


def _command(description: str, date: str, app: str = "4013") -> dict:
    return {
        "name": "command-setLevel",
        "description": f"Command called: {description}",
        "date": date,
        "type": "command",
        "producedBy": {
            "id": app,
            "type": "app",
            "label": "Bathroom (💡 Lights On, 🏃 Motion Active)",
        },
    }


def _switch(value: str, date: str) -> dict:
    return {
        "name": "switch", "value": value, "date": date,
        "isStateChange": True, "type": "physical",
        "producedBy": {"id": "7790", "label": "Matter Hue Bridge Pro", "type": "device"},
    }


def _focus() -> dict:
    return {
        "subject": "Bathroom Light 1", "action": "on",
        "boundaryRole": "start", "open": True,
        "stateBoundary": "2026-10-12T07:08:06.273+0100",
        "command": {
            "date": "2026-10-12T07:08:06.165+0100",
            "display": "setLevel(30)",
            "level": 30,
            "semantics": "level-switch-command",
        },
        "producer": {
            "id": "4013", "type": "app",
            "label": "Bathroom (💡 Lights On, 🏃 Motion Active)",
        },
        "competingCommands": [],
    }


def _evidence() -> list[dict]:
    return [{
        "tool": "homebrain_device_history", "success": True,
        "details": {
            "label": "Bathroom Light 1", "attribute": "switch",
            "temporalAnalysis": {
                "observedIntervals": [
                    {
                        "start": "2026-10-12T02:53:50.265+0100",
                        "end": "2026-10-12T03:05:01.466+0100",
                    },
                    {
                        "start": "2026-10-12T06:45:20.237+0100",
                        "end": "2026-10-12T06:56:52.638+0100",
                    },
                ],
                "openActiveStart": "2026-10-12T07:08:06.273+0100",
                "openActiveInterval": True,
            },
            "commandEvents": [
                _command("setLevel(50)", "2026-10-12T07:15:02.086+0100"),
                _command("setLevel(30)", "2026-10-12T07:08:06.165+0100"),
                _command("setLevel(30)", "2026-10-12T06:45:20.349+0100"),
                _command("setLevel(30)", "2026-10-12T06:45:20.287+0100"),
                _command("setLevel(10)", "2026-10-12T02:53:50.297+0100"),
                _command("setLevel(10)", "2026-10-12T02:53:49.268+0100"),
            ],
            "correlationEvents": [
                _switch("on", "2026-10-12T07:08:06.273+0100"),
                _switch("off", "2026-10-12T06:56:52.638+0100"),
                _switch("on", "2026-10-12T06:45:20.237+0100"),
                _switch("off", "2026-10-12T03:05:01.466+0100"),
                _switch("on", "2026-10-12T02:53:50.265+0100"),
            ],
        },
    }]


def test_custom_automation_label_does_not_block_proven_setlevel_followup():
    # The producer naming must not depend on the literal word 'lighting'.
    evidence = _evidence()
    event = evidence[0]["details"]["commandEvents"][1]
    event["description"] = "Command called: setLevel(30)"
    evidence[0]["details"]["boundaryEvents"] = [
        _switch("on", "2026-10-12T07:08:06.273+0100"),
    ]
    focus = proven_lighting_command(evidence)
    assert focus is not None
    assert focus["producer"]["id"] == "4013"
    assert focus["command"]["semantics"] == "level-switch-command"


def test_explains_earlier_levels_and_later_dimming_without_new_activation():
    description = render_level_command_pattern(_evidence(), _focus())
    assert description
    assert "02:53:50 (10%)" in description
    assert "06:45:20 (30%)" in description
    assert description.count("06:45:20 (30%)") == 1
    assert "07:15:02" in description
    assert "not another switch-on" in description
    assert "plausible but not verified" in description


def _sensor(label: str, room: str, id_: str) -> dict:
    return {
        "id": id_, "label": label, "room": room,
        "capabilities": ["MotionSensor"], "attributes": {"motion": "active"},
    }


def test_unique_room_occupancy_is_a_bounded_candidate_without_configuration():
    identities = [
        _sensor("LWR01 Bathroom Occupancy", "Bathroom", "7007"),
        _sensor("Hallway Motion", "Hallway", "7008"),
    ]
    chosen = choose_occupancy_event_sources(
        identities, config_search="", subject_room="Bathroom"
    )
    assert len(chosen) == 1
    assert chosen[0][0]["id"] == "7007"
    assert chosen[0][1] == "motion"
    assert chosen[0][2] is False


def test_multiple_ambiguous_room_sensors_do_not_produce_guessed_trigger():
    identities = [
        _sensor("Bathroom Motion 1", "Bathroom", "7007"),
        _sensor("Bathroom Motion 2", "Bathroom", "7009"),
    ]
    assert choose_occupancy_event_sources(
        identities, config_search="", subject_room="Bathroom"
    ) == []
    chosen = choose_occupancy_event_sources(
        identities,
        config_search="Bathroom Motion 2 is configured",
        subject_room="Bathroom",
    )
    assert len(chosen) == 1 and chosen[0][0]["id"] == "7009"


def test_occupancy_edge_is_reported_as_correlation_not_certain_cause():
    text = render_occupancy_edge_correlation(
        _focus(),
        label="LWR01 Bathroom Occupancy",
        attribute="motion",
        event_data={"events": [{
            "name": "motion", "value": "active",
            "date": "2026-10-12T07:08:06.450+0100",
        }]},
    )
    assert text and "LWR01 Bathroom Occupancy" in text
    assert "0.18s after" in text
    assert "timing alone cannot establish" in text
    assert render_occupancy_edge_correlation(
        _focus(), label="LWR01 Bathroom Occupancy", attribute="motion",
        event_data={"events": [{
            "name": "motion", "value": "active",
            "date": "2026-10-12T07:08:16.450+0100",
        }]},
    ) is None
