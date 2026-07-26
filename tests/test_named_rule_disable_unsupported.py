from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from named_rule_disable_guard import _raw_rule_state


def test_raw_rule_state_keeps_disabled_and_paused_distinct():
    state = _raw_rule_state(
        {
            "rules": [
                {
                    "id": 2844,
                    "disabled": False,
                    "paused": True,
                    "status": "paused",
                }
            ]
        },
        2844,
    )

    assert state == {
        "disabled": False,
        "paused": True,
        "status": "paused",
    }


def test_raw_rule_state_derives_status_when_missing():
    disabled = _raw_rule_state({"rules": [{"id": 1, "disabled": True, "paused": False}]}, 1)
    active = _raw_rule_state({"rules": [{"id": 2, "disabled": False, "paused": False}]}, 2)

    assert disabled["status"] == "disabled"
    assert active["status"] == "active"
