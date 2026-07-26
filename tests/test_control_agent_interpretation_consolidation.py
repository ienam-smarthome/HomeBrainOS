from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import control_agent_combined_level as interpretation


REMOVED_MODULES = (
    "control_agent_claude_first",
    "control_agent_goal_based",
    "control_agent_semantic_target",
)


def test_control_interpretation_has_one_module_owner() -> None:
    assert (APP / "control_agent_combined_level.py").is_file()
    for module_name in REMOVED_MODULES:
        assert not (APP / f"{module_name}.py").exists()


def test_interpretation_patch_points_use_the_consolidated_module() -> None:
    assert interpretation.control_agent_claude_first is interpretation
    assert interpretation.claude is interpretation
    assert interpretation.parse_natural_level.__module__ == interpretation.__name__
    assert interpretation.install_goal_based_control.__module__ == interpretation.__name__
    assert interpretation.decompose_natural_target.__module__ == interpretation.__name__


def test_private_normalizers_keep_distinct_semantics() -> None:
    assert interpretation._normalise("  Living ROOM  ") == "living room"
    assert interpretation._semantic_normalise("Living-Room/One") == "Living Room One"
