from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_index_broker import IndexedMCPStateBroker  # noqa: E402


def test_search_fields_only_use_current_hubitat_schema_names():
    assert "type" not in IndexedMCPStateBroker.SEARCH_FIELDS
    assert "deviceType" not in IndexedMCPStateBroker.SEARCH_FIELDS
    assert set(IndexedMCPStateBroker.SEARCH_FIELDS) <= {
        "attributes",
        "capabilities",
        "commands",
        "currentStates",
        "deviceNetworkId",
        "disabled",
        "id",
        "label",
        "lastActivity",
        "mcpManaged",
        "name",
        "parentDeviceId",
        "room",
    }


def test_schema_field_intersection_drops_unknown_fields():
    tool = SimpleNamespace(
        input_schema={
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {"enum": ["id", "label", "room", "currentStates"]},
                }
            }
        }
    )
    selected = IndexedMCPStateBroker._schema_supported_fields(
        tool, ["id", "label", "type", "deviceType", "room", "currentStates"]
    )
    assert selected == ["id", "label", "room", "currentStates"]
