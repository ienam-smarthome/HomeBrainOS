"""A targeted rule's history must never trigger the all-automations inventory shortcut."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rootfs" / "app"))
from automation_status_service import AutomationStatusService


def test_targeted_history_and_logs_are_not_inventory():
    for question in (
        "Show me the recent history of the Livingroom lighting automation. Read-only.",
        "Show history of the Livingroom Light 1 rule.",
        "Show events for Bedroom 1 lighting automation",
        "List recent logs for app 4019",
        "Which events triggered my Livingroom lighting rule?",
    ):
        chosen = AutomationStatusService.matches_request(question)
        assert not chosen, (
            question,
            getattr(AutomationStatusService.matches_request, "__module__", "?"),
            getattr(getattr(AutomationStatusService.matches_request, "__code__", None),
                    "co_filename", "?"),
        )


def test_explicit_population_inventory_still_supported():
    for question in (
        "Show my active automations",
        "List disabled rules",
        "Show broken automations",
        "Which automations are paused?",
    ):
        assert AutomationStatusService.matches_request(question), question
