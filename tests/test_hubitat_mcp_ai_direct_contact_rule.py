from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_direct_contact import (  # noqa: E402
    parse_device_search,
    parse_direct_contact_rule,
)
import hybrid_assistant_mode  # noqa: E402


def test_direct_contact_rule_accepts_spoken_punctuation_device_name():
    parsed = parse_direct_contact_rule(
        "Write a rule to alert when front.door has been left open"
    )
    assert parsed == {
        "requested_device": "front door",
        "duration_seconds": 120,
    }


def test_direct_contact_rule_accepts_explicit_duration():
    parsed = parse_direct_contact_rule(
        "Create an automation to notify me when the Fridge Door is open for 5 minutes"
    )
    assert parsed == {
        "requested_device": "Fridge Door",
        "duration_seconds": 300,
    }


def test_direct_contact_rule_accepts_send_alert_wording_from_mobile_ui():
    parsed = parse_direct_contact_rule(
        "Write a rule to send alert when front door has been left open for 2mins"
    )
    assert parsed == {
        "requested_device": "front door",
        "duration_seconds": 120,
    }


def test_direct_contact_rule_accepts_more_than_duration_wording():
    parsed = parse_direct_contact_rule(
        "write a rule to send a alert when front door has been left open for more than 2 mins"
    )
    assert parsed == {
        "requested_device": "front door",
        "duration_seconds": 120,
    }
    assert parse_direct_contact_rule(
        "Create a rule to notify me when Front Door is open for longer than 3 minutes"
    )["duration_seconds"] == 180
    assert parse_direct_contact_rule(
        "Create a rule to notify me when Front Door is open for over 30 seconds"
    )["duration_seconds"] == 30


def test_find_device_query_is_claimed_by_selected_device_search():
    assert parse_device_search("Find front door") == "front door"
    assert parse_device_search("Search for device front.door") == "front door"


def test_specialist_requests_do_not_reach_ai_evidence_planner():
    assert not hybrid_assistant_mode.is_hybrid_ai_query("Find front door")
    assert not hybrid_assistant_mode.is_hybrid_ai_query(
        "Write a rule to send alert when front door has been left open for 2mins"
    )
    assert not hybrid_assistant_mode.is_hybrid_ai_query(
        "write a rule to send a alert when front door has been left open for more than 2 mins"
    )


def test_unrelated_rule_language_is_not_claimed():
    assert parse_direct_contact_rule("Write a rule to turn lights on at sunset") is None
    assert parse_direct_contact_rule("Why is the front door open?") is None
