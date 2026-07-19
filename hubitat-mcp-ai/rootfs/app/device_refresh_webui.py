from __future__ import annotations

from typing import Any, Callable


PatchPage = Callable[[str], str]


def install_device_refresh_webui(module: Any) -> PatchPage:
    """Rename the catalogue action and route it through the full refresh API."""

    original: PatchPage = module.patch_page

    def patch_page(page: str) -> str:
        page = original(page)
        page = page.replace(
            'id="deviceCatalogue">Device catalogue</button>',
            'id="deviceCatalogue">Refresh Hubitat devices</button>',
        )
        page = page.replace(
            "fetch('api/device-catalogue?force=true')",
            "fetch('api/device-catalogue/refresh',{method:'POST'})",
        )
        page = page.replace(
            "message:`Indexed ${data.selected_count||0} selected Hubitat devices.`",
            "message:`Refreshed ${data.selected_count||0} selected Hubitat devices from Hubitat.`",
        )
        page = page.replace(
            "title:'Device intelligence catalogue'",
            "title:'Hubitat devices refreshed'",
        )
        page = page.replace(
            "subtitle:`Refreshed ${Number(data.last_refresh_age_seconds||0).toFixed(1)}s ago · ${data.rooms?.length||0} rooms`",
            "subtitle:`Live refresh complete · ${data.cache_entries_removed||0} cached reads cleared · ${data.rooms?.length||0} rooms`",
        )
        page = page.replace(
            "note:'The dashboard, device status and device-type questions now share this cached live-state index. A successful control command invalidates it before the next read.'",
            "note:'This action clears shared Hubitat device-state caches, reloads selected-device membership and detailed metadata, and invalidates dashboard counters before the next read.'",
        )
        return page

    module.patch_page = patch_page
    return patch_page


__all__ = ["install_device_refresh_webui"]
