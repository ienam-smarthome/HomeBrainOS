from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mutation_result_policy import enforce_device_mutation_result  # noqa: E402


def test_successful_search_cannot_hide_failed_device_writes():
    answer = enforce_device_mutation_result(
        "turn it off",
        {
            "success": True,
            "message": "I've turned off the hallway lights.",
            "tools_used": [
                {"name": "hub_manage_devices", "success": False},
                {"name": "hub_manage_devices", "success": False},
                {"name": "homebrain_search_devices", "success": True},
            ],
        },
    )

    assert answer["success"] is False
    assert answer["intent"] == "device-control-failed"
    assert answer["message"].startswith("No device command was completed")
    assert answer["mutation_policy_corrected"] is True


def test_successful_device_write_is_preserved():
    original = {
        "success": True,
        "message": "The light is confirmed off.",
        "tools_used": [{"name": "hub_call_device_command", "success": True}],
    }
    assert enforce_device_mutation_result("turn the lamp off", original) == original


def test_read_only_search_cannot_claim_that_a_light_was_turned_off():
    answer = enforce_device_mutation_result(
        "Turn off the second hallway light",
        {
            "success": True,
            "message": "I've turned off Hallway Light 2.",
            "tools_used": [
                {"name": "homebrain_search_devices", "success": True},
                {"name": "hub_list_devices", "success": True},
            ],
        },
    )

    assert answer["success"] is False
    assert answer["submitted"] is False
    assert answer["intent"] == "device-control-not-executed"
    assert "No device command was executed" in answer["message"]
    assert answer["original_message"] == "I've turned off Hallway Light 2."


def test_safe_unresolved_control_response_is_preserved_without_a_write():
    original = {
        "success": False,
        "intent": "control-agent-unresolved",
        "message": "Which hallway light did you mean?",
        "tools_used": [],
    }
    assert enforce_device_mutation_result("turn off the hallway light", original) == original


def test_mixed_device_write_results_are_reported_as_partial():
    answer = enforce_device_mutation_result(
        "turn off both lamps",
        {
            "success": True,
            "message": "Done.",
            "tools_used": [
                {"name": "hub_call_device_command", "success": True},
                {"name": "hub_call_device_command", "success": False},
            ],
        },
    )
    assert answer["success"] is False
    assert answer["intent"] == "device-control-partial"
    assert "1 failed" in answer["message"]
