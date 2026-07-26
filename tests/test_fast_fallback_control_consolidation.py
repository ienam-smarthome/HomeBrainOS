from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from fast_fallback_extended_reads import FastFallbackRouter as ExtendedReadsRouter
from fast_fallback_light_usage import (
    CapabilityDeviceRouter,
    CompatibleDeviceTypeRouter,
    DeviceTypeFastFallbackRouter,
    EngagementFastFallbackRouter,
    FastFallbackRouter,
    IndexedDeviceRouter,
    MultiControlRouter,
    PrayerTimesRouter,
    base_device_label,
    extract_prayer_times,
    split_explicit_control_targets,
)


REMOVED_MODULES = (
    "fast_fallback_prayer_times",
    "fast_fallback_device_types",
    "fast_fallback_device_types_compat",
    "fast_fallback_device_types_live",
    "fast_fallback_device_index",
    "fast_fallback_engagement",
    "fast_fallback_multi_control",
)


def test_control_capabilities_have_one_module_owner() -> None:
    assert (APP / "fast_fallback_light_usage.py").is_file()
    for module_name in REMOVED_MODULES:
        assert not (APP / f"{module_name}.py").exists()


def test_control_router_stage_order_is_preserved() -> None:
    assert PrayerTimesRouter.__bases__ == (ExtendedReadsRouter,)
    assert DeviceTypeFastFallbackRouter.__bases__ == (PrayerTimesRouter,)
    assert CompatibleDeviceTypeRouter.__bases__ == (DeviceTypeFastFallbackRouter,)
    assert CapabilityDeviceRouter.__bases__ == (CompatibleDeviceTypeRouter,)
    assert IndexedDeviceRouter.__bases__ == (CapabilityDeviceRouter,)
    assert EngagementFastFallbackRouter.__bases__ == (IndexedDeviceRouter,)
    assert MultiControlRouter.__bases__ == (EngagementFastFallbackRouter,)
    assert FastFallbackRouter.__bases__ == (MultiControlRouter,)


def test_consolidated_public_helpers_remain_available() -> None:
    assert split_explicit_control_targets("Kitchen Lamp and Hall Lamp") == [
        "Kitchen Lamp",
        "Hall Lamp",
    ]
    assert base_device_label("Kitchen Lamp (Kitchen)") == "kitchen lamp"
    assert extract_prayer_times({"fajr": "03:11"})["Fajr"] == "03:11"
