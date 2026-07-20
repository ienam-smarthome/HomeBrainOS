from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_direct_contact import parse_direct_contact_rule  # noqa: E402


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


def test_unrelated_rule_language_is_not_claimed():
    assert parse_direct_contact_rule("Write a rule to turn lights on at sunset") is None
    assert parse_direct_contact_rule("Why is the front door open?") is None
