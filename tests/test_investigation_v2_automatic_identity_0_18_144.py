"""Regression: V2 should not turn a planner's device name into manual authority.

These tests use synthetic Hubitat inventory; they never contact the hub or
execute device commands.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP))

from investigation_v2.test_service import (
    resolve_planned_device_subjects,
    resolve_verified_device_subjects,
)

DEVICES = [
    {"id": "7103", "name": "Bedroom 3 Mesh", "label": "Bedroom 3 Mesh"},
    {"id": "7104", "name": "Bedroom 3 PC", "label": "Bedroom 3 PC"},
    {"id": "7805", "name": "Livingroom Light 1", "label": "Livingroom Light 1"},
    {"id": "7806", "name": "Livingroom Light 2", "label": "Livingroom Light 2"},
]


def test_full_user_name_beats_short_or_wrong_ai_name():
    question = "Investigate Bedroom 3 Mesh, check the watchdog and MQTT status."
    for guessed in ("Bedroom 3", "Bedroom 3 PC", "No such device"):
        ids, targets, source = resolve_planned_device_subjects(
            question, DEVICES, model_device_name=guessed)
        assert ids == ("7103",)
        assert targets == [{"id": "7103", "label": "Bedroom 3 Mesh"}]
        assert source == "question"


def test_model_name_fallback_requires_unique_live_inventory_identity():
    result = resolve_planned_device_subjects(
        "Why is my network socket offline?", DEVICES,
        model_device_name="Bedroom 3 Mesh")
    assert result[0] == ("7103",)
    assert result[2] == "model_name_verified"
    with pytest.raises(ValueError, match="uniquely"):
        resolve_planned_device_subjects(
            "Why is my network socket offline?", DEVICES,
            model_device_name="Bedroom 3")


def test_duplicate_live_names_remain_ambiguous_without_auto_guessing():
    duplicate = DEVICES + [{"id": "9999", "label": "Bedroom 3 Mesh"}]
    with pytest.raises(ValueError, match="Ambiguous device name"):
        resolve_planned_device_subjects(
            "Why was Bedroom 3 Mesh offline?", duplicate,
            model_device_name="Bedroom 3 Mesh")
    with pytest.raises(ValueError, match="uniquely"):
        resolve_verified_device_subjects(
            "Why?", duplicate, device_name="Bedroom 3 Mesh")
    ids, _, method = resolve_verified_device_subjects(
        "Why?", duplicate, device_ids=["7103"])
    assert ids == ("7103",)
    assert method == "manual_id"


def test_multiple_device_mentions_are_not_silently_narrowed_by_ai_guess():
    ids, _, source = resolve_planned_device_subjects(
        "Compare Bedroom 3 Mesh with Bedroom 3 PC", DEVICES,
        model_device_name="Bedroom 3 Mesh")
    assert ids == ("7103", "7104")
    assert source == "question"


