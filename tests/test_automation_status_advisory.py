from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_status_service import AutomationStatusService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


# --- matches_request / is_advisory_request -------------------------------
#
# Found live: "Recommend useful automations for my home" fell through the
# deterministic automation-status gate entirely (no "list"/"show"/"which"/
# "status"/"active"/"disabled"/"paused"/"broken" word present) and ended up
# in the generic model loop, which took 11.8s and then refused outright
# because the only evidence it produced wasn't marked as live-claim-
# supporting. The gate needed to recognise advisory-intent phrasing too.

def test_advisory_phrasing_now_matches_the_gate():
    assert AutomationStatusService.matches_request(
        "Recommend useful automations for my home"
    ) is True
    assert AutomationStatusService.is_advisory_request(
        "Recommend useful automations for my home"
    ) is True


def test_literal_status_phrasing_still_matches_but_is_not_advisory():
    prompt = (
        "List every automation app and Rule Machine rule with its current "
        "active, disabled, paused, broken, or unknown status"
    )
    assert AutomationStatusService.matches_request(prompt) is True
    assert AutomationStatusService.is_advisory_request(prompt) is False


def test_advisory_words_alone_without_subject_do_not_match():
    # "recommend" with no automation/rule/app subject shouldn't hijack
    # an unrelated request.
    assert AutomationStatusService.matches_request("recommend a good tv show") is False


def test_enable_disable_exclusion_still_applies_to_advisory_phrasing():
    assert AutomationStatusService.matches_request(
        "enable the disabled automation, don't just recommend it"
    ) is False


# --- advisory message builder ---------------------------------------------

def test_advisory_message_highlights_broken_and_disabled_as_actionable():
    items = [
        {"name": "Broken Rule", "display_name": "Broken Rule", "type": "app", "status": "broken"},
        {"name": "Old Automation", "display_name": "Old Automation", "type": "app", "status": "disabled"},
        {"name": "Fine Rule", "display_name": "Fine Rule", "type": "app", "status": "active"},
    ]

    message = AutomationStatusService._advisory_message(items)

    assert "3 automation apps and Rule Machine rules" in message
    assert "Worth fixing first (broken)" in message
    assert "Broken Rule" in message
    assert "Currently disabled" in message
    assert "Old Automation" in message
    # Active items aren't listed individually in the advisory view -- only
    # counted -- since they need no action.
    assert "Fine Rule" not in message


def test_advisory_message_is_honest_about_not_inventing_new_ideas():
    items = [{"name": "X", "display_name": "X", "type": "app", "status": "active"}]

    message = AutomationStatusService._advisory_message(items)

    assert "brand-new automation ideas" in message
    assert "nothing obviously broken or disabled to fix" in message


def test_advisory_message_truncates_long_disabled_lists():
    items = [
        {"name": f"Disabled {i}", "display_name": f"Disabled {i}", "type": "app", "status": "disabled"}
        for i in range(15)
    ]

    message = AutomationStatusService._advisory_message(items)

    assert "...and 5 more disabled." in message


def test_advisory_message_handles_empty_inventory():
    message = AutomationStatusService._advisory_message([])
    assert "nothing to review yet" in message


# --- safety-device gap analysis --------------------------------------------
#
# Added after the user compared the plain advisory output against a
# reference example that did real gap analysis (e.g. "no water leak
# alerting -- these sensors have WaterSensor capability but nothing
# monitors them"). This cross-references real device capabilities against
# real automation names -- a name-match heuristic, not certainty, but
# fully grounded in retrieved data with nothing invented.

WATER_SENSOR_DEVICE = {
    "id": "5387", "label": "Linptech Kitchen lux",
    "capabilities": ["RelativeHumidityMeasurement", "MotionSensor", "ContactSensor",
                      "WaterSensor", "SmokeDetector", "CarbonMonoxideDetector", "Sensor"],
}
NON_SAFETY_DEVICE = {
    "id": "3957", "label": "Fridge", "capabilities": ["Actuator", "Switch", "Sensor"],
}


def test_uncovered_safety_devices_flags_devices_with_no_matching_automation():
    uncovered = AutomationStatusService._uncovered_safety_devices(
        [WATER_SENSOR_DEVICE, NON_SAFETY_DEVICE],
        [{"name": "Unrelated Rule", "display_name": "Unrelated Rule", "status": "active"}],
    )

    labels = [label for label, _caps in uncovered]
    assert "Linptech Kitchen lux" in labels
    assert "Fridge" not in labels  # no safety capability at all


def test_uncovered_safety_devices_excludes_devices_named_by_an_automation():
    uncovered = AutomationStatusService._uncovered_safety_devices(
        [WATER_SENSOR_DEVICE],
        [{"name": "Linptech Kitchen lux leak alert", "display_name": "Linptech Kitchen lux leak alert", "status": "active"}],
    )

    assert uncovered == []


def test_advisory_message_includes_gap_analysis_when_devices_are_passed():
    items = [{"name": "Unrelated Rule", "display_name": "Unrelated Rule", "type": "app", "status": "active"}]

    message = AutomationStatusService._advisory_message(items, [WATER_SENSOR_DEVICE])

    assert "Real gap" in message
    assert "Linptech Kitchen lux" in message
    assert "WaterSensor" in message


def test_advisory_message_omits_gap_section_when_no_devices_passed():
    items = [{"name": "Unrelated Rule", "display_name": "Unrelated Rule", "type": "app", "status": "active"}]

    message = AutomationStatusService._advisory_message(items)

    assert "Real gap" not in message


# --- snapshot() integration ------------------------------------------------
#
# snapshot() itself had zero test coverage before this change (only its
# pure helper methods were tested). The advisory=True path now makes an
# extra hub_read_devices call that wasn't there before -- worth covering
# directly rather than relying only on the pure-function tests above.

class FakeAutomationMCP:
    def __init__(self, apps, rules, devices):
        self.apps = apps
        self.rules = rules
        self.devices = devices
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "hub_read_apps_code":
            return MCPToolResult(name, arguments, {}, "", {"apps": self.apps})
        if name == "hub_read_rules":
            return MCPToolResult(name, arguments, {}, "", {"rules": self.rules})
        if name == "hub_read_devices":
            return MCPToolResult(name, arguments, {}, "", {"devices": self.devices})
        raise AssertionError(("unexpected tool call", name, arguments))


def test_snapshot_advisory_fetches_devices_and_includes_gap_analysis():
    mcp = FakeAutomationMCP(
        apps=[{"id": "1", "name": "Unrelated Rule", "label": "Unrelated Rule", "disabled": False}],
        rules=[],
        devices=[WATER_SENSOR_DEVICE],
    )
    service = AutomationStatusService(mcp)

    outcome = asyncio.run(service.snapshot(advisory=True))

    assert "Real gap" in outcome.message
    assert "Linptech Kitchen lux" in outcome.message
    assert ("hub_read_devices", {"tool": "hub_list_devices", "args": {}}) in mcp.calls


def test_snapshot_literal_does_not_fetch_devices():
    mcp = FakeAutomationMCP(
        apps=[{"id": "1", "name": "Unrelated Rule", "label": "Unrelated Rule", "disabled": False}],
        rules=[],
        devices=[WATER_SENSOR_DEVICE],
    )
    service = AutomationStatusService(mcp)

    outcome = asyncio.run(service.snapshot(advisory=False))

    assert "Real gap" not in outcome.message
    device_calls = [call for call in mcp.calls if call[0] == "hub_read_devices"]
    assert device_calls == []
