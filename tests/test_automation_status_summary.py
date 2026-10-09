from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_status_service import AutomationStatusService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


def test_display_name_removes_duplicate_problem_markers():
    assert AutomationStatusService.display_name("Rule (Paused)") == "Rule"
    assert AutomationStatusService.display_name("Rule *BROKEN*") == "Rule"
    assert AutomationStatusService.display_name("Rule (Paused) *BROKEN*") == "Rule"


def test_status_counts_include_all_known_statuses():
    counts = AutomationStatusService.status_counts(
        [
            {"status": "active"},
            {"status": "broken"},
            {"status": "paused"},
            {"status": "unexpected"},
        ]
    )

    assert counts == {
        "active": 1,
        "disabled": 0,
        "paused": 1,
        "broken": 1,
        "unknown": 1,
    }


def test_message_is_problem_first_and_includes_attention_count():
    items = [
        {"name": "Normal", "display_name": "Normal", "type": "app", "status": "active"},
        {"name": "Paused (Paused)", "display_name": "Paused", "type": "rule", "status": "paused"},
        {"name": "Broken *BROKEN*", "display_name": "Broken", "type": "rule", "status": "broken"},
        {"name": "Unknown", "display_name": "Unknown", "type": "app", "status": "unknown"},
    ]

    message = AutomationStatusService._message(items)

    assert message.startswith("Hubitat returned 4 automation items. 3 need attention.")
    assert "Inventory: 2 app instances, 2 Rule Machine entries." in message
    assert message.index("### Broken (1)") < message.index("### Paused (1)")
    assert message.index("### Paused (1)") < message.index("### Unknown (1)")
    assert message.index("### Unknown (1)") < message.index("### Active (1)")
    assert "*BROKEN*" not in message
    assert "(Paused)" not in message


def test_normalised_item_preserves_broken_status_reason_and_evidence():
    result = MCPToolResult(
        "hub_read_apps_code",
        {},
        {},
        "",
        {
            "apps": [
                {
                    "id": "42",
                    "name": "Lighting: bedroom 3 low light",
                    "broken": True,
                    "statusMessage": "Referenced device no longer exists",
                }
            ]
        },
    )

    item = AutomationStatusService._items_from_result(
        result,
        item_type="app",
        source="hub_read_apps_code",
    )[0]

    assert item["status"] == "broken"
    assert item["status_reason"] == "Referenced device no longer exists"
    assert item["status_evidence"]["broken"] == "True"


def test_broken_name_marker_is_not_claimed_to_be_verified_runtime_failure():
    items = [
        {
            "id": "2957", "name": "Tuya Button: button 3 pushed *BROKEN*",
            "display_name": "Tuya Button: button 3 pushed", "type": "app",
            "status": "broken",
            "status_reason": "Hubitat marked the automation name *BROKEN*.",
        },
        {
            "id": "2958", "name": "Tuya Button: button 4 pushed",
            "display_name": "Tuya Button: button 4 pushed", "type": "app",
            "status": "active",
        },
    ]
    message = AutomationStatusService._message(items)
    assert "configuration status flags requiring review" not in message
    assert "need attention" in message
    assert "enabled/not-disabled does not prove" in message
    assert "invalid actions and missing dependencies were not verified" in message
    assert "(app) [ID 2957] [Hubitat name marker; cause unverified]" in message
    assert "(app) [ID 2958]" in message
    assert "ID 2597" not in message


def test_explicit_broken_signal_is_not_relabelled_as_weak_name_marker():
    message = AutomationStatusService._message([
        {
            "id": "2957", "name": "Button 3", "display_name": "Button 3",
            "type": "app", "status": "broken",
            "status_reason": "Hubitat reports broken=true.",
        },
    ])
    assert "(app) [ID 2957]" in message
    assert "[Hubitat name marker; cause unverified]" not in message


def test_brief_broken_automation_reply_avoids_full_inventory():
    items = [
        {"id": str(i), "name": f"App {i}", "display_name": f"App {i}",
         "type": "app", "status": "active"}
        for i in range(136)
    ]
    items += [
        {"id": str(i), "name": f"Disabled {i}", "display_name": f"Disabled {i}",
         "type": "app", "status": "disabled"}
        for i in range(136, 154)
    ]
    message = AutomationStatusService._brief_message(
        items, rule_coverage="0 entries returned; completeness unverified"
    )
    assert "No broken markers detected among 154 installed app instances" in message
    assert "136 not disabled, 18 disabled" in message
    assert "completeness unverified" in message
    assert "App 1" not in message


def test_brief_broken_automation_reply_identifies_current_ids():
    items = [{"id": "2957", "name": "Button 3 *BROKEN*",
              "display_name": "Button 3", "type": "app", "status": "broken"}]
    message = AutomationStatusService._brief_message(
        items, rule_coverage="unavailable (tool failed)"
    )
    assert "ID 2957" in message
    assert "unavailable (tool failed)" in message
    assert "ID 2597" not in message
