from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from rule_authoring_service import RuleAuthoringService
from tool_registry import rule_machine_proposal_error


def test_relative_one_time_rule_revalidates_without_original_prompt() -> None:
    create = RuleAuthoringService._action(
        name="Block Media Google TV Streamer (One-time 2026-10-02 22:26)",
        at_time="2026-10-02T22:26:12",
        device_id="6923",
        capability_filter="Switch",
        command="blockInternet",
    )

    assert rule_machine_proposal_error("hub_manage_rule_machine", create) is None
