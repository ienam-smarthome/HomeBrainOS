from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_target_resolver import (  # noqa: E402
    normalized_name,
    resolve_device_candidate,
)


LIGHTS = [
    {"id": "1", "label": "Livingroom Light 1"},
    {"id": "2", "label": "Livingroom Light 2"},
    {"id": "3", "label": "Bedroom 1 Light"},
    {"id": "4", "label": "My Floor Lamp"},
    {"id": "5", "label": "Bedroom 2 Light"},
    {"id": "6", "label": "Bedroom 3 Light"},
    {"id": "7", "label": "Big lamp"},
    {"id": "8", "label": "Hallway Light 1"},
    {"id": "9", "label": "Hallway Light 2"},
    {"id": "10", "label": "Bathroom Light 1"},
    {"id": "11", "label": "Bathroom Light 2"},
    {"id": "12", "label": "Shower Light"},
    {"id": "13", "label": "Toilet Light"},
]


def test_normalization_handles_room_spacing_and_spoken_numbers():
    assert normalized_name("living room light two") == "livingroomlight2"
    assert normalized_name("Livingroom Light 2") == "livingroomlight2"


def test_unique_filtered_candidate_accepts_decorated_state_label():
    resolution = resolve_device_candidate(
        "livingroom light 2",
        [{
            "id": "2",
            "displayName": "Livingroom Light 2 (Lights Off)",
        }],
    )

    assert resolution.target["id"] == "2"
    assert resolution.confidence == 1.0


def test_typo_selects_numbered_light_with_clear_margin():
    resolution = resolve_device_candidate(
        "livingrum light two",
        LIGHTS[:2],
    )

    assert resolution.target["id"] == "2"
    assert resolution.confidence >= 0.86


def test_ambiguous_unnumbered_request_fails_with_choices():
    resolution = resolve_device_candidate(
        "hallway light",
        [LIGHTS[7], LIGHTS[8]],
    )

    assert resolution.target is None
    assert resolution.alternatives == (
        "Hallway Light 1",
        "Hallway Light 2",
    )
    assert "ambiguous" in resolution.reason


def test_low_similarity_unique_candidate_is_not_blindly_selected():
    resolution = resolve_device_candidate(
        "kitchen ceiling",
        [{"id": "13", "label": "Toilet Light"}],
    )

    assert resolution.target is None
    assert resolution.confidence < 0.72

