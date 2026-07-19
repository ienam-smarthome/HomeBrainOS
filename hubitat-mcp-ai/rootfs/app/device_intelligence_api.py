from __future__ import annotations

from typing import Any

import device_intelligence_webui as device_intelligence_webui_module
from device_intelligence_index import DeviceIntelligenceIndex
from device_refresh_webui import install_device_refresh_webui


async def refresh_selected_devices(index: DeviceIntelligenceIndex) -> dict[str, Any]:
    """Clear shared device state, then rebuild the selected-device catalogue.

    The device index normally sits behind ``IndexedMCPStateBroker``. Invalidating
    that broker clears cached Hubitat device reads and notifies both the shared
    device index and dashboard snapshot. The forced diagnostics read then reloads
    the compact selected-device membership and detailed metadata before returning.
    """

    broker = getattr(index, "client", None)
    invalidate = getattr(broker, "invalidate", None)
    removed = 0
    if callable(invalidate):
        removed = int(await invalidate("devices") or 0)
    else:
        await index.invalidate()

    diagnostics = dict(await index.diagnostics(force=True))
    diagnostics.update(
        {
            "refresh_scope": "selected-devices",
            "cache_entries_removed": removed,
        }
    )
    return diagnostics


def install_device_intelligence_api(
    application: Any,
    index: DeviceIntelligenceIndex,
) -> None:
    install_device_refresh_webui(device_intelligence_webui_module)

    @application.app.get("/api/device-catalogue", response_model=None)
    async def device_catalogue(force: bool = False):
        if force:
            return await refresh_selected_devices(index)
        return await index.diagnostics(force=False)

    @application.app.post("/api/device-catalogue/refresh", response_model=None)
    async def refresh_device_catalogue():
        return await refresh_selected_devices(index)

    @application.app.get("/api/device-index", response_model=None)
    async def device_index_status():
        return index.stats()


__all__ = [
    "install_device_intelligence_api",
    "refresh_selected_devices",
]
