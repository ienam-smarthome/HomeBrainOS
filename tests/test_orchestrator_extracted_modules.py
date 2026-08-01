from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_agent_orchestrator import UnifiedMCPAgent  # noqa: E402
from request_classification import (  # noqa: E402
    matches,
    requests_mutation,
    routine_control_arguments,
)
from tool_registry import (  # noqa: E402
    LOCAL_CONTROL_TOOL,
    LOCAL_HOME_SNAPSHOT_TOOL,
    control_devices_tool,
    home_snapshot_tool,
)


def test_request_classification_helpers_remain_available_through_agent_shims():
    assert matches("Turn the hallway lights off", {"light"}) is True
    assert requests_mutation("Turn the hallway lights off") is True
    assert routine_control_arguments("Turn the hallway lights off") == {
        "device_names": ["the hallway lights"],
        "device_kind": "auto",
        "command": "off",
    }
    assert UnifiedMCPAgent._requests_mutation("Turn the hallway lights off") is True
    assert UnifiedMCPAgent._routine_control_arguments("Turn the hallway lights off") == {
        "device_names": ["the hallway lights"],
        "device_kind": "auto",
        "command": "off",
    }


def test_tool_registry_builders_preserve_names_and_annotations():
    control = control_devices_tool()
    snapshot = home_snapshot_tool()

    assert control.name == LOCAL_CONTROL_TOOL
    assert control.annotations == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "mutates": True,
        "danger": "routine",
    }
    assert snapshot.name == LOCAL_HOME_SNAPSHOT_TOOL
    assert snapshot.annotations == {"readOnlyHint": True}
