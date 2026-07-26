from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from named_rule_status_route import _state_message, parse_rule_status_target


def test_status_query_requires_explicit_rule_word():
    assert parse_rule_status_target("status of fridge freezer rule") == "fridge freezer rule"
    assert parse_rule_status_target("is fridge freezer rule paused") == "fridge freezer rule"
    assert parse_rule_status_target("status of fridge freezer") is None


def test_paused_and_disabled_states_are_not_conflated():
    paused = _state_message(
        "Appliance: Fridge and Freezer - Auto ON",
        {"disabled": False, "paused": True, "status": "paused"},
    )
    disabled = _state_message(
        "Appliance: Fridge and Freezer - Auto ON",
        {"disabled": True, "paused": False, "status": "disabled"},
    )

    assert "paused but not disabled" in paused
    assert "is disabled" in disabled
    assert "paused but not disabled" not in disabled


def test_active_state_requires_both_flags_false():
    message = _state_message(
        "Appliance: Fridge and Freezer - Auto ON",
        {"disabled": False, "paused": False, "status": "active"},
    )

    assert "is active" in message
    assert "enabled and not paused" in message
