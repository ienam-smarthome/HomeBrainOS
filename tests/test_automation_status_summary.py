from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_status_service import AutomationStatusService  # noqa: E402


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
    assert message.index("### Broken (1)") < message.index("### Paused (1)")
    assert message.index("### Paused (1)") < message.index("### Unknown (1)")
    assert message.index("### Unknown (1)") < message.index("### Active (1)")
    assert "*BROKEN*" not in message
    assert "(Paused)" not in message
