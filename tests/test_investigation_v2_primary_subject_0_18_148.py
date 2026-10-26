"""v0.18.148: original long V2 question must retain its named subject.

Regression tests use synthetic Hubitat inventories only; they cannot access
the live hub or assert what the real devices 5381/7776 are named.
"""
from __future__ import annotations
from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.test_service import (
    resolve_planned_device_subjects, resolve_verified_device_subjects,
)

QUESTION = (
    "Investigate why Bedroom 3 Mesh is offline while MQTT reports connected. "
    "Establish the last genuine message received from the physical device, "
    "when the outage began, and the events or commands preceding it. "
    "Examine current device status, historical switch events, watchdog "
    "behaviour, relevant driver configuration and automation evidence where "
    "supported. Distinguish confirmed observations, likely causes and "
    "remaining uncertainties. Explain what should be checked or corrected. "
    "Do not change anything."
)

SUBJECT = {"id": "7103", "label": "Bedroom 3 Mesh", "name": "Tasmota Smart Plug"}
CONTEXT = [
    {"id": "5381", "label": "Status Helper A",
     "name": "current device status"},
    {"id": "7776", "label": "Status Helper B",
     "name": "current device status"},
    {"id": "5555", "label": "Recent Events", "name": "historical switch events"},
    {"id": "5556", "label": "Other Recent Events", "name": "historical switch events"},
]


def test_original_question_ignores_later_ambiguous_contextual_aliases():
    ids, devices, method = resolve_verified_device_subjects(
        QUESTION, [SUBJECT, *CONTEXT])
    assert ids == ("7103",)
    assert devices == [{"id": "7103", "label": "Bedroom 3 Mesh"}]
    assert method == "question"


def test_model_hint_cannot_replace_original_verified_subject_when_context_collides():
    ids, devices, method = resolve_planned_device_subjects(
        QUESTION, [SUBJECT, *CONTEXT],
        model_device_name="Status Helper A")
    assert ids == ("7103",)
    assert devices[0]["label"] == "Bedroom 3 Mesh"
    assert method == "question"


def test_contextual_phrases_matching_duplicate_friendly_labels_do_not_veto_subject():
    rows = [SUBJECT, {"id": "5381", "label": "current device status"},
            {"id": "7776", "label": "current device status"}]
    ids, _, _ = resolve_verified_device_subjects(QUESTION, rows)
    assert ids == ("7103",)


def test_duplication_of_named_subject_itself_still_fails_closed():
    rows = [SUBJECT, *CONTEXT, {
        "id": "9999", "label": "Bedroom 3 Mesh", "name": "Other plug"}]
    with pytest.raises(ValueError, match="Ambiguous device name") as result:
        resolve_verified_device_subjects(QUESTION, rows)
    assert "#7103" in str(result.value)
    assert "#9999" in str(result.value)


def test_ambiguous_phrase_before_only_unique_subject_still_fails_closed():
    rows = [SUBJECT, {"id": "5381", "label": "Current device status"},
            {"id": "7776", "label": "Current device status"}]
    with pytest.raises(ValueError, match="Ambiguous device name"):
        resolve_verified_device_subjects(
            "Current device status compared with Bedroom 3 Mesh", rows)


def test_multi_device_explicit_full_labels_are_preserved():
    rows = [SUBJECT, {"id": "7104", "label": "Bedroom 3 PC", "name": "Tasmota plug"},
            *CONTEXT]
    ids, devices, _ = resolve_verified_device_subjects(
        "Compare Bedroom 3 Mesh with Bedroom 3 PC and inspect current device status",
        rows)
    assert ids == ("7103", "7104")
    assert [d["label"] for d in devices] == ["Bedroom 3 Mesh", "Bedroom 3 PC"]


def test_no_strong_subject_does_not_ignore_duplicate_names():
    with pytest.raises(ValueError, match="Ambiguous device name"):
        resolve_verified_device_subjects("Examine current device status", CONTEXT)


def test_operator_explicit_numeric_id_never_uses_subject_guessing():
    rows = [SUBJECT, *CONTEXT]
    ids, targets, method = resolve_verified_device_subjects(
        QUESTION, rows, device_ids=["7103"])
    assert ids == ("7103",) and method == "manual_id"
    assert targets[0]["label"] == "Bedroom 3 Mesh"


def test_ambiguous_candidate_names_display_safely_instead_of_device_placeholder():
    rows = [{"id": "5381", "label": "Current Device Status"},
            {"id": "7776", "label": "Current Device Status"}]
    with pytest.raises(ValueError, match="Ambiguous device name") as result:
        resolve_verified_device_subjects("Check Current Device Status", rows)
    detail = str(result.value)
    assert "Current Device Status" in detail
    assert "#5381" in detail and "#7776" in detail
    assert "Device (#5381)" not in detail
