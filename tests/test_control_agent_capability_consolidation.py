from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from control_agent_graph import (
    ControlDeviceGraph,
    exact_non_control_matches,
    install_control_graph_capability_filter,
    is_control_capable,
    non_control_public,
)


def test_control_capability_filter_has_one_module_owner() -> None:
    assert (APP / "control_agent_graph.py").is_file()
    assert not (APP / "control_agent_capability_filter.py").exists()


def test_capability_guards_are_owned_by_control_graph() -> None:
    assert ControlDeviceGraph.__module__ == "control_agent_graph"
    assert exact_non_control_matches.__module__ == "control_agent_graph"
    assert install_control_graph_capability_filter.__module__ == "control_agent_graph"
    assert is_control_capable.__module__ == "control_agent_graph"
    assert non_control_public.__module__ == "control_agent_graph"
