from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from deterministic_tool_presenter import present_tool_result  # noqa: E402


def test_filter_presenter_preserves_every_match_and_count():
    message = present_tool_result(
        "homebrain_filter_devices",
        {
            "attribute": "battery",
            "operator": "lte",
            "comparison_value": 20,
            "matches": [
                {"label": "Door", "value": 14},
                {"label": "TRV", "value": 10},
                {"label": "Remote", "value": 20},
            ],
        },
    )

    assert message == (
        "3 devices have battery levels <= 20%: Door (14%), TRV (10%), "
        "and Remote (20%)."
    )


def test_motion_filter_presenter_uses_natural_domain_language():
    message = present_tool_result(
        "homebrain_filter_devices",
        {
            "attribute": "motion",
            "operator": "eq",
            "comparison_value": "active",
            "matches": [
                {
                    "label": "Kitchen Linptech",
                    "room": "Living Room",
                    "value": "active",
                },
                {
                    "label": "Bedroom 3 Presence Sensor",
                    "room": "Bedroom 3",
                    "value": "active",
                },
            ],
        },
    )

    assert message == (
        "2 motion sensors are active: Kitchen Linptech (Living Room) and "
        "Bedroom 3 Presence Sensor (Bedroom 3)."
    )


def test_empty_authoritative_results_are_explicit():
    assert present_tool_result(
        "homebrain_active_lights", {"lights": [], "count": 0}
    ) == "No lights are currently on."
    assert present_tool_result(
        "homebrain_active_rooms", {"active_rooms": [], "count": 0}
    ) == "No rooms are currently active."
    assert present_tool_result(
        "homebrain_active_switches", {"switches": [], "count": 0}
    ) == "No non-light switches are currently on."


def test_failed_local_read_returns_tool_error_without_model_rewrite():
    assert present_tool_result(
        "homebrain_active_rooms",
        {"error": "Live device read failed"},
        failed=True,
    ) == "Live device read failed"


def test_unknown_tools_remain_model_synthesized():
    assert present_tool_result("hub_read_diagnostics", {"logs": []}) is None


def test_hub_info_firmware_snapshot_reports_available_update():
    message = present_tool_result(
        "homebrain_hub_info_snapshot",
        {
            "success": True,
            "scope": "firmware",
            "installed_firmware": "2.5.1.136",
            "available_firmware": "2.5.1.139",
            "update_available": True,
        },
    )

    assert message == (
        "Hub firmware 2.5.1.136 is installed and 2.5.1.139 is available."
    )


def test_hub_info_resources_include_driver_units():
    message = present_tool_result(
        "homebrain_hub_info_snapshot",
        {
            "success": True,
            "scope": "resources",
            "cpu_5_min": 0.81,
            "cpu_percent": 20.25,
            "free_memory": 1.02,
            "free_memory_unit": "GB",
            "temperature": "53.5 °C",
            "temperature_unit": "°C",
            "uptime": "0d:0h:49m:47s",
            "database_size": 243,
            "database_size_unit": "MB",
        },
    )

    assert message == (
        "Hub resources:\n\n"
        "- **CPU load (5 min):** 0.81 / 20.25%\n"
        "- **Free memory:** 1.02 GB\n"
        "- **Temperature:** 53.5 °C\n"
        "- **Uptime:** 0d:0h:49m:47s\n"
        "- **Database size:** 243 MB"
    )


def test_control_presenter_distinguishes_unverified_from_unsent():
    message = present_tool_result(
        "homebrain_control_devices",
        {
            "success": False,
            "failed": [
                {
                    "label": "TV",
                    "command_sent": True,
                    "verified": False,
                },
                {
                    "label": "Socket",
                    "command_sent": False,
                    "verified": None,
                },
            ],
        },
        failed=True,
    )

    assert message == (
        "Command sent but state verification failed: TV. Failed: Socket."
    )
