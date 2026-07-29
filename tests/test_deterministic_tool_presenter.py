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
        "3 devices matched battery <= 20: Door: battery=14, TRV: battery=10, "
        "and Remote: battery=20."
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
