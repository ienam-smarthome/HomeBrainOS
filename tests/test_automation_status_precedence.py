from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_status_service import AutomationStatusService  # noqa: E402


def test_broken_name_overrides_active_and_disabled_signals():
    item = {
        "id": 1,
        "name": "Hallway dimmer: button 1 pushed *BROKEN*",
        "active": True,
        "disabled": True,
    }

    assert AutomationStatusService.normalise_status(item) == "broken"
    assert AutomationStatusService._status_signals(item) == {
        "broken": True,
        "paused": False,
        "disabled": True,
        "active": True,
    }


def test_paused_name_overrides_active_and_disabled_signals():
    item = {
        "id": 2,
        "label": "Appliance: Fridge and Freezer - Auto ON (Paused)",
        "enabled": True,
        "disabled": True,
    }

    assert AutomationStatusService.normalise_status(item) == "paused"
    assert AutomationStatusService._status_signals(item) == {
        "broken": False,
        "paused": True,
        "disabled": True,
        "active": True,
    }


def test_broken_takes_precedence_over_paused():
    item = {
        "id": 3,
        "name": "Example rule (Paused) *BROKEN*",
        "active": True,
    }

    assert AutomationStatusService.normalise_status(item) == "broken"


def test_disabled_still_precedes_generic_active_when_no_problem_marker_exists():
    item = {
        "id": 4,
        "name": "Disabled automation",
        "disabled": True,
        "active": True,
    }

    assert AutomationStatusService.normalise_status(item) == "disabled"


def test_message_groups_items_by_corrected_status():
    items = [
        {"name": "Normal", "type": "app", "status": "active"},
        {"name": "Paused rule", "type": "rule", "status": "paused"},
        {"name": "Broken rule", "type": "rule", "status": "broken"},
    ]

    message = AutomationStatusService._message(items)

    assert "### Active" in message
    assert "- [ACTIVE] Normal (app)" in message
    assert "### Paused" in message
    assert "- [PAUSED] Paused rule (rule)" in message
    assert "### Broken" in message
    assert "- [BROKEN] Broken rule (rule)" in message
