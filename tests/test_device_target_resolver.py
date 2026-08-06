from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_target_resolver import (  # noqa: E402
    normalized_name,
    resolve_device_candidate,
    targeted_name_variants,
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


def test_targeted_variants_share_number_word_and_hyphen_normalization():
    assert targeted_name_variants("Tab S nine") == [
        "tab s 9",
        "tab-s9",
        "tab-s-9",
        "s9",
    ]


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


def test_exact_device_label_outranks_fuzzy_candidates():
    resolution = resolve_device_candidate(
        "TV",
        [
            {"id": "4221", "label": "TV"},
            {"id": "5000", "label": "Block Google-TV-Streamer"},
            {"id": "6000", "label": "Bot"},
        ],
    )

    assert resolution.target["id"] == "4221"
    assert resolution.confidence == 1.0
    assert resolution.reason == "exact normalized name"


def test_duplicate_exact_device_labels_remain_ambiguous():
    resolution = resolve_device_candidate(
        "TV",
        [
            {"id": "4221", "label": "TV"},
            {"id": "4222", "label": "TV"},
        ],
    )

    assert resolution.target is None
    assert "multiple devices exactly" in resolution.reason


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


# A heterogeneous inventory mixing device kinds, mirroring what a real house
# actually looks like -- LIGHTS above is lights-only, which is why the gap
# below was never caught by that fixture: every "wrong kind of device"
# query against a lights-only list still had only lights to be compared
# against, never surfacing the case where several *irrelevant* candidates
# outrank each other without any of them being a plausible match.
MIXED_INVENTORY = [
    {"id": "1", "label": "Hallway Light 1"},
    {"id": "2", "label": "Hallway Light 2"},
    {"id": "3", "label": "Hallway TRV"},
    {"id": "4", "label": "Bedroom 1 TRV"},
    {"id": "5", "label": "Bedroom 2 TRV"},
    {"id": "6", "label": "Fridge"},
    {"id": "7", "label": "Fridge Door"},
    {"id": "8", "label": "Fridge Meter"},
    {"id": "9", "label": "Front Door"},
    {"id": "10", "label": "TV"},
]


def test_genuinely_absent_device_type_is_missing_not_ambiguous():
    """A device category that doesn't exist at all must not be reported as
    ambiguous just because *something* scores highest among irrelevant
    candidates. Found via live testing against a real 84-device house: a
    request for a nonexistent "Garage Door" was resolving as ambiguous
    among Fridge Door / Front Door / Bedroom 1 TRV at confidence 0.69 --
    exactly the score the token-incompatibility penalty in _score() is
    meant to signal as "not a real match", but nothing downstream was
    checking that floor once more than one candidate existed.
    """

    for absent_query in (
        "Garage Door",
        "EV Charger",
        "Swimming pool pump",
        "Sprinkler",
    ):
        resolution = resolve_device_candidate(absent_query, MIXED_INVENTORY)
        assert resolution.target is None, absent_query
        assert resolution.confidence < 0.70, absent_query
        assert "confidence floor" in resolution.reason, absent_query


def test_same_kind_ambiguity_is_unaffected_by_the_missing_floor():
    """The fix above must not turn genuine same-kind ambiguity into a false
    "missing" result -- these score well above the floor and should still
    surface as a choice between real candidates.
    """

    lights = resolve_device_candidate("Hallway Light", MIXED_INVENTORY)
    assert lights.target is None
    assert lights.confidence >= 0.86
    assert "Hallway Light 1" in lights.alternatives
    assert "Hallway Light 2" in lights.alternatives

    trvs = resolve_device_candidate("TRV", MIXED_INVENTORY)
    assert trvs.target is None
    assert trvs.confidence >= 0.86
    assert "Hallway TRV" in trvs.alternatives


def test_exact_and_semantic_matches_still_resolve_in_mixed_inventory():
    exact = resolve_device_candidate("Fridge", MIXED_INVENTORY)
    assert exact.target is not None
    assert exact.target["label"] == "Fridge"

    front_door = resolve_device_candidate("Front Door", MIXED_INVENTORY)
    assert front_door.target is not None
    assert front_door.target["label"] == "Front Door"
