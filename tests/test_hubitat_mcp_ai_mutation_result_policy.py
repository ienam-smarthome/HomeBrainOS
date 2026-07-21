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
