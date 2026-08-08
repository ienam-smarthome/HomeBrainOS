"""0.10.379 hardening pass: exhaustive coverage for internet-block/allow
requests, built from the real live house inventory (see
tests/fixtures/live_devices_2026-08-08.json) rather than synthetic
fixtures alone, plus the model-fallback hand-off added so that phrasing
the deterministic parsers do not recognise still resolves the correct
device instead of repeating the original "block the tv" -> power-off
mistake.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_target_resolver import resolve_capable_device_candidate  # noqa: E402
from request_classification import parse_immediate_internet_access_intent  # noqa: E402
from tool_registry import device_resolver_tool  # noqa: E402


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "live_devices_2026-08-08.json"
LIVE_DEVICES = json.loads(FIXTURE_PATH.read_text())["devices"]


def test_resolver_tool_schema_exposes_required_command_to_the_model():
    """The model's only general-purpose device-lookup tool must be able to
    ask for capability-scoped resolution directly -- otherwise a novel
    phrasing the deterministic parsers don't recognise has no way to avoid
    the same "exact name wins over capability" trap that caused the
    original live bug.
    """

    tool = device_resolver_tool()
    properties = tool.input_schema["properties"]

    assert "required_command" in properties
    assert properties["required_command"]["type"] == "string"
    assert "required" not in tool.input_schema or "required_command" not in tool.input_schema["required"]
    assert "blockInternet" in tool.description
    assert "TV" in tool.description


def test_all_five_live_internet_blockable_devices_resolve_by_their_distinguishing_word():
    """Every real internet-blockable device in the house, resolved by the
    word that actually distinguishes it, must find itself -- and only
    itself -- once capability scoping is applied. This is the general
    regression test the "TV" bug should have had from the start: it
    exercises the whole real inventory, not just the one pair that was
    reported live.
    """

    expectations = {
        "tab s9": "Block Tab-S9-FE",
        "nucbox": "Block PC-NucBox-M6Ultra",
        "tv": "Block Google-TV-Streamer",
        "streamer": "Block Google-TV-Streamer",
        "camera g100 42ea": "Block CAM-Camera-G100-42EA",
        "camera g100 7b37": "Block CAM-Camera-G100-7B37",
    }
    for query, expected_label in expectations.items():
        resolution = resolve_capable_device_candidate(
            query, LIVE_DEVICES, required_command="blockInternet",
        )
        assert resolution.target is not None, query
        assert resolution.target["label"] == expected_label, query


def test_pc_resolves_to_the_capable_device_not_the_same_named_mqtt_socket():
    """Regression test for a second real naming collision found in the live
    inventory while hardening the "TV" fix: "Block PC-NucBox-M6Ultra" is
    the only device supporting blockInternet, but the house also has an
    unrelated MQTT-controlled outlet literally labelled "Bedroom3 PC
    (MQTT)". Capability scoping must exclude it before name matching ever
    runs, the same way it already does for "TV".
    """

    resolution = resolve_capable_device_candidate(
        "pc", LIVE_DEVICES, required_command="blockInternet",
    )

    assert resolution.target is not None
    assert resolution.target["label"] == "Block PC-NucBox-M6Ultra"
    assert resolution.target["id"] == "6917"


def test_cam_alone_is_genuinely_ambiguous_between_the_two_real_cameras():
    """Unlike "pc" and "tv", "cam" alone is genuinely ambiguous: the house
    has two real camera-blocking devices (G100-42EA and G100-7B37) and no
    single-candidate answer would be honest. This must surface as a choice
    between the two real cameras, not silently pick one, and must not
    include the unrelated "HallwayCAM (MQTT)" socket (filtered out by
    capability scoping) as a phantom third option.
    """

    resolution = resolve_capable_device_candidate(
        "cam", LIVE_DEVICES, required_command="blockInternet",
    )

    assert resolution.target is None
    assert "HallwayCAM (MQTT)" not in resolution.alternatives


def test_immediate_parser_recognises_restrict_and_explicit_unblock_restore():
    """Hardening pass addition: "restrict" is an unambiguous internet-access
    synonym for "block" and is safe to accept the same way "disable"
    already is. "unblock"/"restore" are NOT safe to accept as loosely --
    both words are heavily overloaded elsewhere (a hub backup can be
    "restored") -- so they only count as internet-access requests when
    "internet"/"access" is stated explicitly.
    """

    assert parse_immediate_internet_access_intent("restrict the tv") == (
        "tv", "blockInternet",
    )
    assert parse_immediate_internet_access_intent(
        "restrict internet access for the tv"
    ) == ("tv", "blockInternet")
    assert parse_immediate_internet_access_intent(
        "unblock internet access for the tv"
    ) == ("tv", "allowInternet")
    assert parse_immediate_internet_access_intent(
        "restore internet access for the tv"
    ) == ("tv", "allowInternet")
    assert parse_immediate_internet_access_intent(
        "restore access for the tv"
    ) == ("tv", "allowInternet")


def test_bare_unblock_or_restore_without_internet_wording_is_never_hijacked():
    """The exact failure mode the stricter explicit-clause requirement
    exists to prevent: "restore the backup" (a real, unrelated hub
    operation) must never be reinterpreted as "unblock a device named
    backup" just because "restore" is also a valid internet-access verb
    when paired with explicit "internet"/"access" wording.
    """

    assert parse_immediate_internet_access_intent("restore the backup") is None
    assert parse_immediate_internet_access_intent("restore default settings") is None
    assert parse_immediate_internet_access_intent("unblock the front door") is None
