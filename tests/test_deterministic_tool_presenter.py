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
        "3 devices have battery levels at or below 20%: Door (14%), TRV (10%), "
        "and Remote (20%)."
    )


def test_filter_presenter_uses_speech_friendly_comparisons():
    expected_phrases = {
        "eq": "temperature equal to 20",
        "ne": "temperature not equal to 20",
        "lt": "temperature below 20",
        "lte": "temperature at or below 20",
        "gt": "temperature above 20",
        "gte": "temperature at or above 20",
    }

    for operator, phrase in expected_phrases.items():
        message = present_tool_result(
            "homebrain_filter_devices",
            {
                "attribute": "temperature",
                "operator": operator,
                "comparison_value": 20,
                "matches": [],
            },
        )
        assert message == f"No devices matched {phrase}."


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
        "2 motion sensors are active: Kitchen Linptech and "
        "Bedroom 3 Presence Sensor."
    )


def test_active_lights_omit_redundant_room_names():
    message = present_tool_result(
        "homebrain_active_lights",
        {
            "lights": [
                {"label": "Bedroom 3 Light", "room": "Bedroom 3"},
                {"label": "Livingroom Light 1", "room": "Living Room"},
            ],
        },
    )

    assert message == (
        "2 lights are on: Bedroom 3 Light and Livingroom Light 1."
    )


def test_active_rooms_omit_internal_reason_details():
    message = present_tool_result(
        "homebrain_active_rooms",
        {
            "active_rooms": [
                {"name": "Bedroom 3", "reasons": ["light on", "motion"]},
                {"name": "Living Room", "reasons": ["motion"]},
            ],
        },
    )

    assert message == "2 rooms are active: Bedroom 3 and Living Room."


def test_many_active_switches_are_grouped_by_room():
    message = present_tool_result(
        "homebrain_active_switches",
        {
            "switches": [
                {"label": "Fridge", "room": "Appliances"},
                {"label": "Freezer", "room": "Appliances"},
                {"label": "TV", "room": "Multimedia"},
                {"label": "Computer", "room": "Multimedia"},
                {"label": "Nest Mini socket", "room": "Sockets"},
                {"label": "LivCAM socket", "room": "Sockets"},
            ],
        },
    )

    assert message == (
        "6 non-light switches are on:\n\n"
        "- **Appliances:** Fridge and Freezer\n"
        "- **Multimedia:** TV and Computer\n"
        "- **Sockets:** Nest Mini socket and LivCAM socket"
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


def test_hub_info_resources_do_not_duplicate_a_unit_already_baked_into_free_memory_or_database_size():
    """Regression test: the temperature field was already guarded against a
    baked-in unit producing a duplicate ("46.9 °C °C" was a live bug), but
    free_memory and database_size had no equivalent guard even though they
    go through the identical hub_info_service.py passthrough. If either
    ever arrives pre-suffixed with its unit, it must not be doubled.
    """

    message = present_tool_result(
        "homebrain_hub_info_snapshot",
        {
            "success": True,
            "scope": "resources",
            "free_memory": "512 MB",
            "free_memory_unit": "MB",
            "database_size": "1.2 GB",
            "database_size_unit": "GB",
        },
    )

    assert "MB MB" not in message
    assert "GB GB" not in message
    assert "**Free memory:** 512 MB" in message
    assert "**Database size:** 1.2 GB" in message


def test_hub_info_firmware_snapshot_treats_a_string_update_available_correctly():
    """Regression test: Hubitat/upstream tool results consistently transmit
    boolean-ish flags as the strings "true"/"false" rather than a JSON
    boolean (already confirmed live for zbHealthy/zwHealthy). A bare
    bool(x) on the string "false" is truthy in Python -- this must not
    falsely claim an update is available when update_available == "false".
    """

    up_to_date = present_tool_result(
        "homebrain_hub_info_snapshot",
        {
            "success": True,
            "scope": "firmware",
            "installed_firmware": "2.5.1.147",
            "available_firmware": "2.5.1.147",
            "update_available": "false",
        },
    )
    assert up_to_date == "Hub firmware 2.5.1.147 is up to date."

    update_pending = present_tool_result(
        "homebrain_hub_info_snapshot",
        {
            "success": True,
            "scope": "firmware",
            "installed_firmware": "2.5.1.145",
            "available_firmware": "2.5.1.147",
            "update_available": "true",
        },
    )
    assert update_pending == (
        "Hub firmware 2.5.1.145 is installed and 2.5.1.147 is available."
    )


def test_control_presenter_treats_a_string_success_flag_correctly():
    """Regression test: `not data.get("success")` on the string "false" is
    False (non-empty strings are truthy in Python), so a failed control
    command reported with success="false" would render as if it had
    succeeded. This must be treated as a failure.
    """

    message = present_tool_result(
        "homebrain_control_devices",
        {
            "success": "false",
            "failed": [
                {"label": "Kitchen Light", "command_sent": False},
            ],
        },
    )

    assert "Failed: Kitchen Light" in message
    assert "Turned" not in message


def test_device_history_presenter_treats_a_string_success_flag_as_failure():
    """Regression test: `data.get("success") is False` is a strict identity
    check that never matches the string "false" -- a failed history lookup
    reported that way would fall through to success-formatting instead of
    the error path.
    """

    message = present_tool_result(
        "homebrain_device_history",
        {"success": "false", "label": "Front Door", "alternatives": []},
    )

    assert "could not read event history" in message.casefold()


def test_control_presenter_treats_a_string_changed_flag_correctly():
    """Regression test: `x.get("changed", True)` truthy-checked directly
    would treat the string "false" as truthy, misreporting an
    already-in-state device as freshly changed.
    """

    message = present_tool_result(
        "homebrain_control_devices",
        {
            "success": True,
            "command": "off",
            "succeeded": [
                {"label": "Toilet Light", "id": "1", "changed": "false"},
            ],
        },
    )

    assert "Nothing to do" in message
    assert "already off" in message


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


def test_control_presenter_separates_changed_from_already_in_state():
    """Regression test for a live report: "turn off the lights" hit every
    real light in the house and reported all of them as "Turned off", even
    ones that were already off -- reading as if the assistant had no idea
    which lights were actually on. Devices device_control_service.py marks
    with changed=False (its cached/live pre-state already matched the
    requested command) must be split out into their own clause instead of
    being named alongside the ones that actually flipped state.
    """

    message = present_tool_result(
        "homebrain_control_devices",
        {
            "success": True,
            "command": "off",
            "succeeded": [
                {"label": "Kitchen Light", "changed": True},
                {"label": "Bedroom 1 Light", "changed": True},
                {"label": "Toilet Light", "changed": False},
                {"label": "Hallway Light 1", "changed": False},
            ],
            "failed": [],
        },
    )

    assert message == (
        "Turned off Kitchen Light and Bedroom 1 Light. "
        "2 were already off: Toilet Light and Hallway Light 1."
    )


def test_control_presenter_reports_nothing_to_do_when_everything_already_matched():
    message = present_tool_result(
        "homebrain_control_devices",
        {
            "success": True,
            "command": "off",
            "succeeded": [
                {"label": "Toilet Light", "changed": False},
            ],
            "failed": [],
        },
    )

    assert message == "Nothing to do -- every matched device was already off."


def test_control_presenter_without_changed_flags_keeps_prior_wording():
    """A result with no "changed" key at all (an older caller, or a device
    whose prior state genuinely could not be determined) must fall back to
    naming every succeeded device exactly as before this change -- silence
    on the flag must never be read as "already in state".
    """

    message = present_tool_result(
        "homebrain_control_devices",
        {
            "success": True,
            "command": "off",
            "succeeded": [
                {"label": "Hallway Light 1"},
                {"label": "Hallway Light 2"},
            ],
            "failed": [],
        },
    )

    assert message == "Turned off Hallway Light 1 and Hallway Light 2."
