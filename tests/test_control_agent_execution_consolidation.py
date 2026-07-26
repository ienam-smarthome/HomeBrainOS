from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from control_agent_rescue import (
    ControlContextStore,
    FastVerifiedControlAgent,
    HomeBrainControlAgent,
    LearnedAliasStore,
    PendingControlStore,
    RescueControlAgent,
    install_base_control_agent,
    install_control_agent,
    install_verified_control_agent,
)


REMOVED_MODULES = (
    "control_agent",
    "control_agent_level_verified",
    "control_agent_state",
)


def test_control_execution_has_one_module_owner() -> None:
    assert (APP / "control_agent_rescue.py").is_file()
    for module_name in REMOVED_MODULES:
        assert not (APP / f"{module_name}.py").exists()


def test_control_execution_stage_order_is_preserved() -> None:
    assert FastVerifiedControlAgent.__bases__ == (HomeBrainControlAgent,)
    assert RescueControlAgent.__bases__ == (FastVerifiedControlAgent,)


def test_state_and_installers_are_owned_by_rescue_module() -> None:
    assert ControlContextStore.__module__ == "control_agent_rescue"
    assert PendingControlStore.__module__ == "control_agent_rescue"
    assert LearnedAliasStore.__module__ == "control_agent_rescue"
    assert install_base_control_agent.__module__ == "control_agent_rescue"
    assert install_verified_control_agent.__module__ == "control_agent_rescue"
    assert install_control_agent.__module__ == "control_agent_rescue"
