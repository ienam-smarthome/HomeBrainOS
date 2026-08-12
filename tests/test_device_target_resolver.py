from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_target_resolver import (  # noqa: E402
    device_commands,
    normalized_name,
    resolve_capable_device_candidate,
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


def test_missing_resolution_reports_no_alternatives_not_below_floor_padding():
    """Regression test for a live failure: "what's the whole house power"
    was misrouted into device-name resolution (fixed separately in
    contextual_read_fast_path.py), scored near-zero against every device,
    and the "missing" branch still handed back ranked[:3]'s arbitrary,
    below-floor tie-break order as "alternatives" -- which the caller
    (homebrain_agent.py) turns into a "Which device do you mean: ..."
    clarification regardless of why the resolution came back empty. That
    surfaced completely unrelated devices ("Front Door", "Google
    Chromecast+") as if they were plausible guesses. A missing resolution
    (nothing cleared the confidence floor) must report zero alternatives,
    not just a low confidence score.
    """

    inventory = [
        {"id": "1", "label": "Front Door"},
        {"id": "2", "label": "Google Chromecast+"},
        {"id": "3", "label": "Weather Open-Meteo"},
        {"id": "4", "label": "Shower Light"},
    ]

    resolution = resolve_device_candidate("whole house power", inventory)

    assert resolution.target is None
    assert resolution.alternatives == ()


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


def test_ambiguous_choices_never_pad_with_an_implausible_third_candidate():
    """Regression test for a real live failure: "turn off the lamp" against
    a house with two real lamps ("Big lamp", "My Floor Lamp", both scoring
    0.9) surfaced "HallwayCAM (MQTT)" -- a camera device with no relation
    to lamps, scoring only 0.43 -- as a third disambiguation choice, purely
    because it happened to score third highest across the whole inventory.
    Every alternative offered to the user for an ambiguous request must
    itself clear the same confidence floor used to reject a genuinely
    absent device category outright.
    """

    inventory = [
        {"id": "1", "label": "Big lamp"},
        {"id": "2", "label": "My Floor Lamp"},
        {"id": "3", "label": "HallwayCAM (MQTT)"},
        {"id": "4", "label": "Bedroom 1 TRV"},
        {"id": "5", "label": "Front Door"},
    ]

    resolution = resolve_device_candidate("the lamp", inventory)

    assert resolution.target is None
    assert resolution.alternatives == ("Big lamp", "My Floor Lamp")
    assert "HallwayCAM (MQTT)" not in resolution.alternatives
    assert "ambiguous" in resolution.reason
    assert "HallwayCAM" not in resolution.reason


def test_exact_and_semantic_matches_still_resolve_in_mixed_inventory():
    exact = resolve_device_candidate("Fridge", MIXED_INVENTORY)
    assert exact.target is not None
    assert exact.target["label"] == "Fridge"

    front_door = resolve_device_candidate("Front Door", MIXED_INVENTORY)
    assert front_door.target is not None
    assert front_door.target["label"] == "Front Door"


def test_hyphenated_device_code_typed_without_hyphens_still_resolves():
    """Regression test for a real live production failure: "block internet
    for tab s9fe" against a device labelled "Block Tab-S9-FE" was declined
    as ambiguous alongside two completely unrelated devices ("Contact
    Sensor", "Tasmota MQTT - Freezer"). The device's own label hyphenates
    the compound code into separate tokens ("tab", "s9", "fe") once
    punctuation is normalised, but nobody types the hyphen when speaking or
    typing the same code ("s9fe" as one token) -- so neither "s9" nor "fe"
    alone was similar enough to "s9fe" for the ordinary per-token typo
    tolerance, capping the score into ambiguous territory even though
    nothing else was a remotely plausible match.
    """

    candidates = [
        {"id": "1", "label": "Block Tab-S9-FE"},
        {"id": "2", "label": "Contact Sensor"},
        {"id": "3", "label": "Tasmota MQTT - Freezer"},
    ]

    resolution = resolve_device_candidate("tab s9fe", candidates)

    assert resolution.target is not None
    assert resolution.target["id"] == "1"
    assert resolution.matched_name == "Block Tab-S9-FE"


def test_dominant_margin_does_not_paper_over_genuine_ambiguity():
    """The new moderate-score/dominant-margin acceptance tier must not
    swallow real ambiguity between two similarly-named candidates -- only
    a truly dominant top score should resolve automatically.
    """

    candidates = [
        {"id": "1", "label": "Hallway Light 1"},
        {"id": "2", "label": "Hallway Light 2"},
    ]

    resolution = resolve_device_candidate("hallway light", candidates)

    assert resolution.target is None
    assert "Hallway Light 1" in resolution.alternatives
    assert "Hallway Light 2" in resolution.alternatives


def test_leading_article_is_stripped_before_scoring_for_a_clean_exact_match():
    # "the fridge" must resolve as a genuine exact match ("Fridge"), not
    # merely squeak past the confidence floor. An earlier, narrower fix
    # only stopped "the" from being scored as a required specific token,
    # which was enough for a long label like "Fridge" but still left the
    # article diluting the underlying similarity score for short labels
    # (see the "the tv" case below) -- the article must be stripped before
    # scoring even starts, not just excluded from the compatibility gate.
    resolution = resolve_device_candidate(
        "the fridge",
        [
            {"id": "3957", "label": "Fridge"},
            {"id": "7105", "label": "Freezer (MQTT)"},
            {"id": "5382", "label": "Bridge#5381 Device#01"},
        ],
    )

    assert resolution.target is not None
    assert resolution.target["id"] == "3957"
    assert resolution.confidence == 1.0
    assert resolution.reason == "exact normalized name"


def test_leading_article_on_a_short_label_does_not_sink_below_the_floor():
    # Regression test for a real live failure found immediately after the
    # first article fix shipped: "turn off the TV" still failed, because a
    # short label like "TV" (2 characters) is dominated by the 3 extra
    # characters of "the" in the raw similarity score, dragging it to 0.57
    # -- well below the confidence floor -- even though "the fridge" (a
    # longer label) had scored high enough to pass. Stripping the article
    # before scoring fixes both cases uniformly instead of depending on
    # how long the label happens to be.
    resolution = resolve_device_candidate(
        "the tv",
        [
            {"id": "4221", "label": "TV"},
            {"id": "5000", "label": "Block Google-TV-Streamer"},
            {"id": "6000", "label": "Tuya Remote (bedroom 3)"},
        ],
    )

    assert resolution.target is not None
    assert resolution.target["id"] == "4221"
    assert resolution.confidence == 1.0


def test_articles_a_and_an_do_not_block_exact_matches_either():
    resolution_a = resolve_device_candidate(
        "a fan",
        [{"id": "1", "label": "Fan"}, {"id": "2", "label": "Standing Fan"}],
    )
    resolution_an = resolve_device_candidate(
        "an oven",
        [{"id": "3", "label": "Oven"}],
    )

    assert resolution_an.target is not None
    assert resolution_an.target["id"] == "3"


def test_device_commands_extracts_names_from_list_or_dict_shapes():
    assert device_commands({"commands": ["on", "off", "blockInternet"]}) == {
        "on", "off", "blockinternet",
    }
    assert device_commands({"commands": [{"name": "blockInternet"}]}) == {"blockinternet"}
    assert device_commands({"supportedCommands": ["setLevel"]}) == {"setlevel"}
    assert device_commands({}) == set()


def test_resolve_capable_device_candidate_prefers_the_capable_device_over_an_exact_name_match():
    """Regression test for a real live failure: a plain power-switch
    labelled exactly "TV" wins ordinary name resolution against "tv"
    every time (exact match, confidence 1.0), even though a second device
    -- "Block Google-TV-Streamer" -- is the only one that actually
    supports blockInternet. Scoping to capable devices before resolving by
    name must find the streamer instead.
    """

    tv_switch = {"id": "4221", "label": "TV", "commands": ["on", "off"]}
    tv_streamer = {
        "id": "6923", "label": "Block Google-TV-Streamer",
        "commands": ["on", "off", "blockInternet", "allowInternet"],
    }

    resolution = resolve_capable_device_candidate(
        "tv", [tv_switch, tv_streamer], required_command="blockInternet"
    )

    assert resolution.target is not None
    assert resolution.target["id"] == "6923"


def test_resolve_capable_device_candidate_reports_missing_not_a_wrong_device():
    tv_switch = {"id": "4221", "label": "TV", "commands": ["on", "off"]}

    resolution = resolve_capable_device_candidate(
        "tv", [tv_switch], required_command="blockInternet"
    )

    assert resolution.target is None
    assert resolution.alternatives == ()
