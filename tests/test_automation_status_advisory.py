from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_status_service import AutomationStatusService  # noqa: E402


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

    assert "not new automation ideas" in message
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
