from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from home_summary_consistency_guard import (  # noqa: E402
    _active_motion_labels,
    _replace_motion_claims,
)


def test_active_motion_summary_uses_all_live_motion_states():
    devices = [
        {
            "label": "Bedroom 1 FP300",
            "currentStates": [{"name": "motion", "currentValue": "active"}],
        },
        {
            "label": "Bedroom 2 FP1",
            "currentStates": {"motion": "active"},
        },
        {
            "label": "Bedroom 3 Presence Sensor",
            "attributes": {"motion": {"value": "active"}},
        },
        {
            "label": "Hallway Motion",
            "currentStates": {"motion": "inactive"},
        },
    ]

    active, states_read = _active_motion_labels(devices)

    assert active == [
        "Bedroom 1 FP300",
        "Bedroom 2 FP1",
        "Bedroom 3 Presence Sensor",
    ]
    assert states_read == 4


def test_incomplete_ai_motion_sentence_is_removed_before_authoritative_text():
    message = (
        "The home is in School Run mode. In the bedrooms, there is active motion "
        "detected in Bedroom 2, while hallway motion is inactive. The living room "
        "is warm."
    )
    authoritative = (
        "Live motion check: 3 motion sensors are active: Bedroom 1 FP300, "
        "Bedroom 2 FP1, and Bedroom 3 Presence Sensor (13 states read)."
    )

    corrected = _replace_motion_claims(message, authoritative)

    assert "active motion detected in Bedroom 2" not in corrected
    assert corrected.endswith(authoritative)
    assert "The home is in School Run mode." in corrected
    assert "The living room is warm." in corrected
