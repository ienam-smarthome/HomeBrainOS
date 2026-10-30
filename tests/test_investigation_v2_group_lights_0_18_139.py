"""V2 category queries are read-only group reads, not mandatory device IDs.

Uses the shared HomeBrain state helper and intentionally verifies that normal
singular/causal/time-specific requests remain on their existing V2 path.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

APP=Path(__file__).resolve().parents[1]/"hubitat-mcp-ai"/"rootfs"/"app"
sys.path.insert(0,str(APP))
from investigation_v2.group_state import (
    current_light_group_question, current_light_group_answer,
)
from investigation_v2.test_service import resolve_verified_device_subjects


@pytest.mark.parametrize(("question","state"),[
    ("which lights are currently on?","on"),
    ("What lights are on right now?","on"),
    ("show me all lamps that are on","on"),
    ("How many lights are ON?","on"),
    ("Are any bulbs on?","on"),
    ("which lights are off?","off"),
    ("List lamps that are OFF","off"),
])
def test_group_read_understood_without_any_named_light(question,state):
    assert current_light_group_question(question)==state


@pytest.mark.parametrize("question",[
    "Why did the livingroom lights remain on overnight?",
    "Turn on all lights",
    "switch the lights off",
    "What lights were on yesterday?",
    "Which lights were on today?",
    "Which lights are on and off?",
    "What was Light 1 doing at 02:00?",
    "Show Livingroom Light 1",
])
def test_does_not_capture_causal_historical_or_device_writes(question):
    assert current_light_group_question(question) is None


DEVICES=[
    {"id":"7805","name":"Livingroom Light 1","label":"Livingroom Light 1",
     "room":"Living Room","capabilities":["Switch","SwitchLevel"],
     "attributes":[{"name":"switch","currentValue":"on"}]},
    {"id":7806,"label":"Livingroom Light 2","room":"Living Room",
     "capabilities":["ColorControl","Switch"],"attributes":{"switch":"off"}},
    {"id":7818,"label":"Bathroom Light 1","room":"Bathroom",
     "currentStates":{"switch":"on"},"capabilities":["Switch"]},
    {"id":5000,"label":"Bedroom Lamp","room":"Bedroom 2",
     "capabilities":["Switch"],"attributes":{"switch":"unknown"}},
    {"id":4221,"label":"TV","room":"Multimedia",
     "capabilities":["Switch"],"currentStates":{"switch":"on"}},
    {"id":6923,"label":"Block Google TV Streamer","room":"Internet",
     "capabilities":["Switch"],"attributes":{"switch":"on"}},
    {"id":9010,"label":"Livingroom Light 1 Controller","room":"Apps",
     "capabilities":["Sensor"],"currentStates":{"switch":"off"}},
]


def test_current_group_query_no_longer_requires_an_individual_id():
    # Old singular resolver cannot infer a unique ID from the question.
    with pytest.raises(ValueError,match="No device name"):
        resolve_verified_device_subjects("which lights are currently on?",DEVICES)
    answer=current_light_group_answer(
        "which lights are currently on?",DEVICES,
        {"source":"fresh_projected_gateway","pages":2,"complete":True},
        checked_at=datetime(2026,10,26,14,42,tzinfo=timezone.utc),
    )
    assert answer["answer_mode"]=="current_group_state"
    text=answer["report"]["text"]
    assert "Hubitat reports 2 light(s) ON" in text
    assert "Bathroom — Bathroom Light 1" in text
    assert "Living Room — Livingroom Light 1" in text
    assert "TV" not in text
    assert "Google TV" not in text
    assert answer["group_status"]["on_count"]==2
    assert answer["group_status"]["off_count"]>=1
    assert answer["group_status"]["unknown_count"]==1
    assert answer["group_status"]["inventory_complete"] is True
    assert answer["resolved_devices"]==[]
    assert "no usable" not in text.lower()
    assert not text.startswith("**")


def test_partial_inventory_never_claims_every_light_is_off():
    result=current_light_group_answer(
        "which lights are currently on?",
        [{"id":"1","label":"Hallway Light","attributes":{"switch":"off"}}],
        {"source":"full_detailed_fallback","pages":1,"complete":False},
    )
    assert result["group_status"]["matched_count"]==0
    assert result["group_status"]["inventory_complete"] is False
    assert "inventory may be incomplete" in result["answer"]["text"]
    assert "guaranteed whole-home count" in result["answer"]["text"]
    assert "live_group_state_coverage_unverified" in result["answer"]["validation_issues"]


def test_missing_switch_is_unknown_not_off_or_zero():
    result=current_light_group_answer("which lights are off?",[
        {"id":9,"label":"Hallway Light","attributes":{}}
    ],{"complete":True})
    assert result["group_status"]["off_count"]==0
    assert result["group_status"]["unknown_count"]==1
    assert "unknown switch state" in result["answer"]["text"]


def test_duplicate_or_unverified_identity_does_not_increase_counts():
    result=current_light_group_answer("which lights are currently on?",[
        {"id":"7805","label":"Livingroom Light","attributes":{"switch":"on"}},
        {"id":"7805","label":"Livingroom Light","attributes":{"switch":"on"}},
        {"id":True,"label":"Fake Light","attributes":{"switch":"on"}},
    ],{"complete":False})
    assert result["group_status"]["on_count"]==1


def test_untrusted_label_cannot_inject_markdown_or_markup():
    result=current_light_group_answer("which lights are on?",[
        {"id":42,"label":"Kitchen | <script>alert(1)</script> *Light*",
         "room":"Kitchen","attributes":{"switch":"on"}},
    ],{"complete":True})
    text=result["report"]["text"]
    assert "<script>" not in text
    assert "|" not in text
    assert "*Light*" not in text


