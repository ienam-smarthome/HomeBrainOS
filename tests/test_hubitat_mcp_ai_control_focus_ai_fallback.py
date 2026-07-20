from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from control_focus_ai_fallback import is_control_safe_ai_read
from control_focus_octopus_energy import (
    is_octopus_display_query,
    is_whole_house_period_query,
    requested_octopus_period,
)


def test_clear_device_controls_never_go_to_ai_read_fallback() -> None:
    assert not is_control_safe_ai_read("Turn on Bedroom 1 Light")
    assert not is_control_safe_ai_read("Set Livingroom Light 1 to 30%")
    assert not is_control_safe_ai_read("Switch off both bathroom lights")


def test_general_read_only_home_questions_can_use_ai_fallback() -> None:
    assert is_control_safe_ai_read("Why is my electricity usage high today?")
    assert is_control_safe_ai_read("Summarise today's energy use")
    assert is_control_safe_ai_read("What should I improve in the bathroom ventilation setup?")
    assert is_control_safe_ai_read("Show me anything unusual with the house")


def test_rule_writes_are_never_sent_to_ai_evidence_planner() -> None:
    assert not is_control_safe_ai_read("Create an automation for the bathroom fan")
    assert not is_control_safe_ai_read("Delete the washing machine rule")
    assert not is_control_safe_ai_read("Repair rule 42")


def test_octopus_family_and_period_queries_stay_deterministic() -> None:
    assert is_octopus_display_query("Show Octopus live meter display")
    assert is_whole_house_period_query("Total power consumption today")
    assert is_whole_house_period_query("Total energy yesterday")
    assert requested_octopus_period("How much energy this week?") == "week"
    assert requested_octopus_period("Octopus standing charge") == "standing charge"
    assert not is_control_safe_ai_read("Show Octopus live meter display")
    assert not is_control_safe_ai_read("Total power consumption today")
