from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_status_service import AutomationStatusService  # noqa: E402


def test_conflicting_statuses_reports_multiple_asserted_states():
    assert AutomationStatusService.conflicting_statuses(
        {"broken": True, "paused": False, "disabled": True, "active": True}
    ) == ["broken", "disabled", "active"]


def test_conflicting_statuses_ignores_single_state():
    assert AutomationStatusService.conflicting_statuses(
        {"broken": False, "paused": True, "disabled": False, "active": False}
    ) == []


def test_message_reports_conflict_count_and_marker():
    items = [
        {
            "name": "Rule *BROKEN*",
            "display_name": "Rule",
            "type": "rule",
            "status": "broken",
            "status_conflict": True,
        }
    ]

    message = AutomationStatusService._message(items)

    assert "1 need attention" in message
    assert "1 have conflicting source-state signals" in message
    assert "[conflicting source state]" in message
