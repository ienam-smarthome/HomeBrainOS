from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_catalogue_safe import (  # noqa: E402
    SafeCapabilityCatalogueDeviceIndex,
)


class FakeIndex(SafeCapabilityCatalogueDeviceIndex):
    def __init__(
        self,
        summary: list[dict[str, Any]],
        metadata: list[dict[str, Any]],
    ) -> None:
        self.summary_rows = summary
        self.metadata_rows = metadata
        self.summary_forces: list[bool] = []
        self.metadata_forces: list[bool] = []
        self.metadata_ttl_seconds = 120.0
        self._snapshot = None
        self._metadata = None
        self._stats = {}

    async def summary_devices(self, *, force: bool = False):
        self.summary_forces.append(force)
        return list(self.summary_rows)

    async def metadata_devices(self, *, force: bool = False):
        self.metadata_forces.append(force)
        return list(self.metadata_rows)


def test_metadata_only_removed_device_is_not_reintroduced_and_live_state_wins():
    index = FakeIndex(
        summary=[
            {
                "id": "1",
                "label": "Hallway Motion",
                "room": "Hallway",
                "currentStates": {"motion": "inactive"},
            }
        ],
        metadata=[
            {
                "id": "1",
                "label": "Hallway Motion",
                "room": "Hallway",
                "capabilities": ["MotionSensor"],
                # Simulate an older detailed metadata record. The compact live
                # summary above must remain authoritative for the same attribute.
                "attributes": {"motion": "active"},
            },
            {
                "id": "2",
                "label": "Seeed Studio MR60BHA2 MQTT",
                "room": "Living Room",
                "capabilities": ["MotionSensor"],
                "attributes": {"motion": "active"},
            },
        ],
    )

    devices = asyncio.run(index.enriched_devices(force=False))

    assert [item["id"] for item in devices] == ["1"]
    assert devices[0]["capabilities"] == ["MotionSensor"]
    assert devices[0]["attributes"]["motion"] == "inactive"
    assert index._last_metadata_orphans_dropped == 1


def test_empty_summary_states_keep_matching_detailed_attributes():
    index = FakeIndex(
        summary=[
            {
                "id": "10",
                "label": "Bedroom Dimmer",
                "room": "Bedroom 1",
                "currentStates": {},
            }
        ],
        metadata=[
            {
                "id": "10",
                "label": "Bedroom Dimmer",
                "room": "Bedroom 1",
                "capabilities": ["Switch", "SwitchLevel"],
                "attributes": {"switch": "on", "level": 45},
            }
        ],
    )

    devices = asyncio.run(index.enriched_devices(force=True))

    assert devices[0]["attributes"] == {"switch": "on", "level": 45}
    assert devices[0]["capabilities"] == ["Switch", "SwitchLevel"]
    assert index.summary_forces == [True]
    assert index.metadata_forces == [True]


def test_dashboard_uses_capabilities_and_excludes_removed_metadata_states():
    index = FakeIndex(
        summary=[
            {
                "id": "1",
                "label": "Ceiling",
                "room": "Hallway",
                "currentStates": {},
            },
            {
                "id": "2",
                "label": "Computer",
                "room": "Bedroom 3",
                "currentStates": {"switch": "on"},
            },
            {
                "id": "3",
                "label": "Hallway Motion",
                "room": "Hallway",
                "currentStates": {"motion": "active", "battery": 19},
            },
        ],
        metadata=[
            {
                "id": "1",
                "label": "Ceiling",
                "room": "Hallway",
                "capabilities": ["Switch", "SwitchLevel"],
                "attributes": {"switch": "on", "level": 80},
            },
            {
                "id": "2",
                "label": "Computer",
                "room": "Bedroom 3",
                "capabilities": ["Switch"],
                "attributes": {"switch": "on"},
            },
            {
                "id": "3",
                "label": "Hallway Motion",
                "room": "Hallway",
                "capabilities": ["MotionSensor", "Battery"],
                "attributes": {"motion": "inactive", "battery": 21},
            },
            {
                "id": "4",
                "label": "Removed Active Sensor",
                "capabilities": ["MotionSensor"],
                "attributes": {"motion": "active"},
            },
        ],
    )

    metrics = asyncio.run(index.dashboard_metrics(force=True))

    assert metrics["selected_devices"] == 3
    assert metrics["lights_on"] == 1
    assert metrics["switches_on"] == 1
    assert metrics["motion_active"] == 1
    assert metrics["low_batteries"] == 1
    assert metrics["metadata_orphans_dropped"] == 1
    assert metrics["state_records"] == 3


def test_release_metadata_is_0416():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (
        ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"
    ).read_text(encoding="utf-8")

    assert "version: '0.4.16-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.16-alpha"' in entrypoint
