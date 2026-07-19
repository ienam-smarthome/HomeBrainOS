from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_api import refresh_selected_devices  # noqa: E402
from device_refresh_webui import install_device_refresh_webui  # noqa: E402


class FakeIndex:
    def __init__(self, *, broker: bool = True) -> None:
        self.events: list[str] = []
        self.client: Any = FakeBroker(self) if broker else object()

    async def invalidate(self) -> None:
        self.events.append("index:invalidate")

    async def diagnostics(self, *, force: bool = False) -> dict[str, Any]:
        self.events.append(f"diagnostics:{force}")
        return {
            "success": True,
            "selected_count": 42,
            "rooms": ["Hallway", "Kitchen"],
            "last_refresh_age_seconds": 0.0,
        }


class FakeBroker:
    def __init__(self, index: FakeIndex) -> None:
        self.index = index

    async def invalidate(self, category: str) -> int:
        self.index.events.append(f"broker:{category}")
        await self.index.invalidate()
        return 3


def test_refresh_invalidates_shared_broker_before_forced_catalogue_reload():
    index = FakeIndex()

    result = asyncio.run(refresh_selected_devices(index))

    assert index.events == [
        "broker:devices",
        "index:invalidate",
        "diagnostics:True",
    ]
    assert result["selected_count"] == 42
    assert result["refresh_scope"] == "selected-devices"
    assert result["cache_entries_removed"] == 3


def test_refresh_falls_back_to_direct_index_invalidation_without_broker():
    index = FakeIndex(broker=False)

    result = asyncio.run(refresh_selected_devices(index))

    assert index.events == ["index:invalidate", "diagnostics:True"]
    assert result["cache_entries_removed"] == 0


def test_webui_action_is_named_and_routed_as_a_full_refresh():
    source = """
    <button class="secondary" id="deviceCatalogue">Device catalogue</button>
    const response=await fetch('api/device-catalogue?force=true');
    message:`Indexed ${data.selected_count||0} selected Hubitat devices.`
    title:'Device intelligence catalogue'
    subtitle:`Refreshed ${Number(data.last_refresh_age_seconds||0).toFixed(1)}s ago · ${data.rooms?.length||0} rooms`
    note:'The dashboard, device status and device-type questions now share this cached live-state index. A successful control command invalidates it before the next read.'
    """
    module = SimpleNamespace(patch_page=lambda page: page)

    install_device_refresh_webui(module)
    page = module.patch_page(source)

    assert "Refresh Hubitat devices</button>" in page
    assert "fetch('api/device-catalogue/refresh',{method:'POST'})" in page
    assert "Refreshed ${data.selected_count||0} selected Hubitat devices from Hubitat." in page
    assert "${data.cache_entries_removed||0} cached reads cleared" in page
    assert "clears shared Hubitat device-state caches" in page
