from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from named_rule_control import NamedRuleController


def test_base_rule_controller_only_maps_pause_and_resume_to_paused_state():
    available = {"hub_set_rule_paused", "hub_set_rule_disabled"}

    pause_tool, pause_args, pause_wording = NamedRuleController._operation("pause", 2844, available)
    disable_tool, disable_args, disable_wording = NamedRuleController._operation("disable", 2844, available)

    assert pause_tool == "hub_set_rule_paused"
    assert pause_args == {"ruleId": 2844, "paused": True}
    assert pause_wording == "pause"

    # The runtime disable guard intercepts disable before this legacy fallback.
    # This assertion documents the old mapping so it cannot silently be relied on.
    assert disable_tool == "hub_set_rule_paused"
    assert disable_args == {"ruleId": 2844, "paused": True}
    assert disable_wording == "pause"


def test_runtime_entrypoint_installs_distinct_rule_disable_guard():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "install_named_rule_disable_guard" in entrypoint
    assert "named_rule_disable_guard = install_named_rule_disable_guard" in entrypoint
