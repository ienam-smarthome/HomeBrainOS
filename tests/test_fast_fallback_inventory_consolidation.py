from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

from fast_fallback_device_health import SpeechFastFallbackRouter  # noqa: E402
from fast_fallback_extended_reads import (  # noqa: E402
    DashboardFastFallbackRouter,
    DeviceStatusRouter,
    EssentialsFastFallbackRouter,
    FastFallbackRouter,
    InventoryFastFallbackRouter,
    ReleaseFastFallbackRouter,
    RoomInventoryRouter,
    _rows,
)


def test_inventory_room_group_has_one_module_owner():
    for module_name in (
        "fast_fallback_inventory",
        "fast_fallback_dashboard",
        "fast_fallback_essentials",
        "fast_fallback_room_inventory",
        "fast_fallback_release",
        "fast_fallback_device_status",
    ):
        assert not (APP_DIR / f"{module_name}.py").exists()
    assert (APP_DIR / "fast_fallback_extended_reads.py").is_file()


def test_consolidated_inventory_read_mro_is_preserved():
    assert InventoryFastFallbackRouter.__bases__ == (SpeechFastFallbackRouter,)
    assert DashboardFastFallbackRouter.__bases__ == (InventoryFastFallbackRouter,)
    assert EssentialsFastFallbackRouter.__bases__ == (DashboardFastFallbackRouter,)
    assert RoomInventoryRouter.__bases__ == (EssentialsFastFallbackRouter,)
    assert ReleaseFastFallbackRouter.__bases__ == (RoomInventoryRouter,)
    assert DeviceStatusRouter.__bases__ == (ReleaseFastFallbackRouter,)
    assert FastFallbackRouter.__bases__ == (DeviceStatusRouter,)
    assert _rows({"devices": [{"id": "1"}]}, ("devices",)) == [{"id": "1"}]
