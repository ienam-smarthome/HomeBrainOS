"""v0.18.147: host-only friendly-label precedence, without ambiguous guesses."""
from __future__ import annotations
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.test_service import (
    resolve_planned_device_subjects, resolve_verified_device_subjects,
)

# Different live Hubitat IDs may expose the same text through a user-defined
# friendly label versus another device's underlying driver/name field.
LIVE = [
    {"id": "7103", "label": "Bedroom 3 Mesh", "name": "Tasmota Smart Plug"},
    {"id": "9001", "label": "Bedroom 3 Mesh Link Status",
     "name": "Bedroom 3 Mesh"},
    {"id": "7104", "label": "Bedroom 3 PC", "name": "Computer MQTT Plug"},
]


def test_question_prefers_exact_friendly_label_over_generic_underlying_name():
    ids, targets, method = resolve_verified_device_subjects(
        "Investigate why Bedroom 3 Mesh is offline while MQTT is connected.", LIVE)
    assert ids == ("7103",)
    assert targets == [{"id": "7103", "label": "Bedroom 3 Mesh"}]
    assert method == "question"


def test_manual_friendly_name_precedence_matches_question_precedence():
    ids, targets, method = resolve_verified_device_subjects(
        "Investigate a fault", LIVE, device_name="bedroom-3 MESH")
    assert ids == ("7103",)
    assert method == "device_name"
    assert targets[0]["label"] == "Bedroom 3 Mesh"


def test_longest_matching_label_still_beats_shorter_overlap():
    ids, targets, _ = resolve_verified_device_subjects(
        "What is Bedroom 3 Mesh Link Status doing?", LIVE)
    assert ids == ("9001",)
    assert targets[0]["label"] == "Bedroom 3 Mesh Link Status"


def test_two_distinct_complete_names_are_both_retained_not_silently_narrowed():
    ids, _, _ = resolve_verified_device_subjects(
        "Compare Bedroom 3 Mesh and Bedroom 3 PC", LIVE)
    assert ids == ("7103", "7104")


def test_model_cannot_override_verified_friendly_name_or_force_second_device():
    ids, targets, source = resolve_planned_device_subjects(
        "Investigate Bedroom 3 Mesh", LIVE, model_device_name="Bedroom 3 Mesh Link Status")
    assert ids == ("7103",)
    assert targets[0]["id"] == "7103"
    assert source == "question"


def test_identical_friendly_labels_remain_unresolvable_and_reveal_safe_ids():
    devices = LIVE + [{"id": "9999", "label": "Bedroom 3 Mesh",
                       "name": "Another Plug"}]
    for kwargs in ({}, {"device_name": "Bedroom 3 Mesh"}):
        with pytest.raises(ValueError, match="Ambiguous device name") as exc:
            resolve_verified_device_subjects(
                "Investigate Bedroom 3 Mesh", devices, **kwargs)
        detail = str(exc.value)
        assert "#7103" in detail and "#9999" in detail
        assert "Advanced options" in detail
        assert "<" not in detail and "password" not in detail.lower()
    ids, _, source = resolve_verified_device_subjects(
        "Investigate Bedroom 3 Mesh", devices, device_ids=["7103"])
    assert ids == ("7103",)
    assert source == "manual_id"


def test_duplicate_underlying_names_with_no_friendly_match_still_ambiguous():
    devices = [
        {"id": "110", "label": "First socket", "name": "Generic MQTT Socket"},
        {"id": "111", "label": "Second socket", "name": "Generic MQTT Socket"},
    ]
    with pytest.raises(ValueError, match="Ambiguous device name") as exc:
        resolve_verified_device_subjects(
            "Investigate Generic MQTT Socket", devices)
    assert "#110" in str(exc.value) and "#111" in str(exc.value)


def test_name_only_device_does_not_outrank_real_friendly_label():
    devices = LIVE + [{"id": "9100", "name": "Bedroom 3 Mesh"}]
    ids, _, _ = resolve_verified_device_subjects(
        "Why is Bedroom 3 Mesh offline?", devices)
    assert ids == ("7103",)


def test_nothing_matching_live_inventory_still_rejected_without_guess():
    with pytest.raises(ValueError, match="No device name"):
        resolve_verified_device_subjects("Investigate an unnamed lamp", LIVE)
