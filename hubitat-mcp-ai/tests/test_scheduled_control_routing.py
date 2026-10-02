from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_classification import routine_control_arguments
from rule_authoring_service import RuleAuthoringService


TARGET = "Block Media-Google-TV-Streamer"


def test_immediate_switch_control_still_uses_fast_path() -> None:
    assert routine_control_arguments(f"turn on {TARGET}") == {
        "device_names": [TARGET],
        "device_kind": "auto",
        "command": "on",
    }


def test_immediate_level_control_is_not_mistaken_for_clock_time() -> None:
    assert routine_control_arguments("set Bedroom 1 Light at 50%") == {
        "device_names": ["Bedroom 1 Light"],
        "device_kind": "light",
        "command": "set_level",
        "level": 50,
    }


@pytest.mark.parametrize(
    "prompt",
    [
        f"turn on {TARGET} at 10pm",
        f"turn on {TARGET} at 22:15",
        f"turn on {TARGET} at noon",
        f"turn on {TARGET} tomorrow",
        f"turn off {TARGET} tonight",
        f"turn on {TARGET} in 30 mins",
        f"turn on {TARGET} after 2 hours",
        f"turn on {TARGET} for 30 minutes",
        f"turn on {TARGET} every day",
        f"turn on {TARGET} on Friday",
        f"toggle {TARGET} at 11.25pm",
    ],
)
def test_future_or_recurring_control_never_compiles_as_immediate(prompt: str) -> None:
    assert routine_control_arguments(prompt) is None


def test_clock_scheduled_control_hands_off_to_rule_authoring() -> None:
    service = RuleAuthoringService(None, lambda *args, **kwargs: None)  # type: ignore[arg-type]

    prompt = f"turn on {TARGET} at 10pm"

    assert routine_control_arguments(prompt) is None
    assert service.matches_request(prompt) is True
