from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from agent_prompt_policy import build_system_prompt
from device_state_summary import active_non_light_switches, internet_access_state


def _switch_device(label: str, room: str, switch: str) -> dict:
    return {
        "id": label,
        "label": label,
        "room": room,
        "capabilities": ["Switch"],
        "attributes": {"switch": switch},
    }


def test_internet_room_on_means_allowed_and_off_means_blocked():
    assert internet_access_state(
        _switch_device("Block Tablet", "Internet", "on")
    ) == "allowed"
    assert internet_access_state(
        _switch_device("Block Tablet", "Internet", "off")
    ) == "blocked"


def test_internet_semantics_come_from_room_not_block_label_prefix():
    assert internet_access_state(
        _switch_device("Block Ordinary Relay", "Utility", "on")
    ) is None
    assert internet_access_state(
        _switch_device("Guest Tablet", "Internet", "off")
    ) == "blocked"


def test_active_internet_switch_keeps_literal_state_and_adds_semantic_state():
    switches = active_non_light_switches(
        [
            _switch_device("Block Tablet", "Internet", "on"),
            _switch_device("Ordinary Socket", "Bedroom", "on"),
            _switch_device("Blocked Tablet", "Internet", "off"),
        ]
    )

    assert len(switches) == 2
    internet = next(item for item in switches if item["label"] == "Block Tablet")
    ordinary = next(item for item in switches if item["label"] == "Ordinary Socket")

    assert internet["switch"] == "on"
    assert internet["semantic_role"] == "internet_access_control"
    assert internet["internet_access"] == "allowed"
    assert internet["state_label"] == "Internet allowed"
    assert "internet_access" not in ordinary


def test_prompt_requires_internet_allowed_blocked_wording_without_command_inversion():
    prompt = build_system_prompt(
        "Device manifest omitted or unavailable.",
        now=datetime(2026, 10, 2, 21, 30, tzinfo=timezone.utc),
    )

    assert 'room/group is exactly "Internet"' in prompt
    assert "switch=on means Internet allowed and switch=off means Internet blocked" in prompt
    assert 'label prefix such as "Block"' in prompt
    assert "Keep the literal Hubitat switch state and underlying on/off commands unchanged" in prompt
