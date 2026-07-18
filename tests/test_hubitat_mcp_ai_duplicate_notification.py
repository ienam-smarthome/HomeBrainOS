from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_rule_workflow_notification_safe import (  # noqa: E402
    NotificationSafeNativeRuleMachineWorkflow,
)
from device_intelligence_duplicate_safe import (  # noqa: E402
    DuplicateAwareCapabilityCatalogueDeviceIndex,
)
from mcp_client import MCPToolResult  # noqa: E402


def tool_result(name: str, data: Any) -> MCPToolResult:
    return MCPToolResult(
        name=name,
        arguments={},
        raw=data,
        text="",
        data=data,
        is_error=False,
    )


class DuplicateIndex(DuplicateAwareCapabilityCatalogueDeviceIndex):
    def __init__(self) -> None:
        pass

    async def summary_devices(self, force: bool = False):
        return [
            {"id": "701", "label": "SM-S938B", "room": "Mobile"},
            {"id": "845", "label": "SM-S938B", "room": "Mobile"},
        ]


class DraftIndex:
    def __init__(self, phone_ids: list[str] | None = None) -> None:
        self.phone_ids = list(phone_ids or ["845"])

    async def exact_device(self, label: str):
        if label == "Fridge Door":
            return {
                "id": "77",
                "label": "Fridge Door",
                "room": "Appliances",
                "currentStates": {"contact": "closed"},
            }, []
        return None, []

    async def enriched_devices(self, force: bool = False):
        # Simulate a gateway catalogue that includes selected phone records but
        # omits capabilities/commands, which previously made the builder miss them.
        return [
            {
                "id": "77",
                "label": "Fridge Door",
                "room": "Appliances",
                "currentStates": {"contact": "closed"},
            },
            *[
                {"id": device_id, "label": "SM-S938B", "room": "Mobile"}
                for device_id in self.phone_ids
            ],
        ]

    async def summary_devices(self, force: bool = False):
        return await self.enriched_devices(force=force)


class NotificationClient:
    configured = True

    def __init__(self, notification_ids: list[str]) -> None:
        self.notification_ids = notification_ids
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        args = dict(arguments or {})
        self.calls.append((name, args))
        assert name == "hub_list_devices"
        assert args.get("capabilityFilter") == "Notification"
        devices = [
            {
                "id": device_id,
                "label": "SM-S938B",
                "room": "Mobile",
                "capabilities": ["Notification"],
                "commands": [{"name": "deviceNotification"}],
            }
            for device_id in self.notification_ids
        ]
        return tool_result(name, {"devices": devices})


RECOMMENDATION = {
    "type": "cold-storage-door",
    "title": "Fridge Door left-open alert",
    "room": "Appliances",
    "devices": ["Fridge Door"],
    "trigger": "Trigger when Fridge Door remains open for 2 minutes.",
    "action": "Send a phone notification and repeat once after 5 minutes.",
    "safeguard": "Cancel the pending repeat when the contact closes.",
}


def test_duplicate_exact_name_lists_device_ids():
    index = DuplicateIndex()
    device, choices = asyncio.run(index.exact_device("SM-S938B"))

    assert device is None
    assert choices == [
        "SM-S938B (ID 701, Mobile)",
        "SM-S938B (ID 845, Mobile)",
    ]


def test_direct_notification_probe_recovers_selected_mobile_device():
    client = NotificationClient(["845"])
    app = SimpleNamespace(mcp=client, VERSION="0.4.20-alpha")
    workflow = NotificationSafeNativeRuleMachineWorkflow(app, DraftIndex(["845"]))

    draft = asyncio.run(workflow._draft(RECOMMENDATION))

    assert draft["unresolved"] == []
    assert draft["notification_candidates"] == [
        {"id": "845", "label": "SM-S938B", "room": "Mobile", "attributes": {}}
    ]
    assert {item["id"] for item in draft["devices"]} == {"77", "845"}
    assert draft["notification_probe"]["matched_ids"] == ["845"]


def test_multiple_notification_devices_show_ids_instead_of_none_found():
    client = NotificationClient(["701", "845"])
    app = SimpleNamespace(mcp=client, VERSION="0.4.20-alpha")
    workflow = NotificationSafeNativeRuleMachineWorkflow(app, DraftIndex(["701", "845"]))

    draft = asyncio.run(workflow._draft(RECOMMENDATION))
    message = " ".join(draft["unresolved"])

    assert "More than one Notification-capable device" in message
    assert "SM-S938B (ID 701, Mobile)" in message
    assert "SM-S938B (ID 845, Mobile)" in message
    assert "No selected Notification-capable device" not in message
