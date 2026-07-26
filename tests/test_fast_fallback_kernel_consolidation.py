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

from fallback_router import HomeBrainFallbackRouter  # noqa: E402
from fast_fallback_live import FastFallbackRouter  # noqa: E402


def test_fast_fallback_kernel_has_one_live_owner():
    assert not (APP_DIR / "fast_fallback.py").exists()
    assert not (APP_DIR / "fast_fallback_weather.py").exists()
    assert (APP_DIR / "fast_fallback_live.py").is_file()
    assert FastFallbackRouter.__bases__ == (HomeBrainFallbackRouter,)


def test_kernel_routes_are_owned_by_the_live_router():
    for method_name in (
        "answer",
        "_execute_catalog_tool",
        "_decorate",
        "_hub_info",
        "_rooms",
        "_rules",
        "_find_weather",
        "_attention",
        "_live_devices",
        "_list_on_devices",
        "_low_batteries",
        "_home_status",
    ):
        assert method_name in FastFallbackRouter.__dict__
