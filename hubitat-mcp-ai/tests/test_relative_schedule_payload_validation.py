from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from tool_registry import rule_machine_proposal_error


def test_dated_trigger_with_direct_action_is_valid_without_prompt_delay_context() -> None:
    proposal = {
        "tool": "hub_set_rule",
        "args": {
            "name": "Block Media Google TV Streamer (One-time 2026-10-02 22:26)",
            "addTrigger": {
                "capability": "Certain Time (and optional date)",
                "time": "A specific time",
                "atTime": "2026-10-02T22:26:12",
            },
            "addAction": {
                "capability": "runCommand",
                "deviceIds": ["6923"],
                "capabilityFilter": "Switch",
                "command": "blockInternet",
            },
        },
    }

    assert rule_machine_proposal_error("hub_manage_rule_machine", proposal) is None
