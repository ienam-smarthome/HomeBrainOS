from __future__ import annotations

from typing import Any

from device_intelligence_index import DeviceIntelligenceIndex


def install_device_intelligence_api(
    application: Any,
    index: DeviceIntelligenceIndex,
) -> None:
    @application.app.get("/api/device-catalogue", response_model=None)
    async def device_catalogue(force: bool = False):
        return await index.diagnostics(force=force)

    @application.app.post("/api/device-catalogue/refresh", response_model=None)
    async def refresh_device_catalogue():
        await index.invalidate()
        return await index.diagnostics(force=True)

    @application.app.get("/api/device-index", response_model=None)
    async def device_index_status():
        return index.stats()


__all__ = ["install_device_intelligence_api"]
