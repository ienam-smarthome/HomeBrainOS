from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from final_read_terminal_routes import (
    build_control_focus_octopus_energy,
    build_device_health_fast_route,
)


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
ENTRYPOINT = APP_DIR / "entrypoint.py"
ENTRYPOINT_CORE = APP_DIR / "entrypoint_core.py"


def run(coro):
    return asyncio.run(coro)


def test_public_entrypoint_registers_health_and_octopus_before_other_read_routes():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    health = source.index('"device-health-fast-route"')
    octopus = source.index('"control-focus-octopus-energy"')
    named_rule = source.index('"named-rule-status"')
    climate = source.index('"climate-metric-extrema"')
    execution = source.index('"execution-contract"')

    assert health < octopus < named_rule < climate < execution
    assert source.count("read_execution_registry.install") == 1


def test_core_keeps_classifier_metadata_but_removes_direct_read_wrappers():
    source = ENTRYPOINT_CORE.read_text(encoding="utf-8")

    assert "configure_device_health_query_classifier()" in source
    assert "configure_octopus_query_classifier()" in source
    assert "install_device_health_fast_route(application)" not in source
    assert "install_control_focus_octopus_energy(application)" not in source
    assert "from device_health_fast_route import install_device_health_fast_route" not in source
    assert "from control_focus_octopus_energy import install_control_focus_octopus_energy" not in source


def test_device_health_route_falls_through_for_unrelated_query():
    application = SimpleNamespace(
        home_snapshot=object(),
        option_bool=lambda name, default: default,
        OPTIONS={},
        VERSION="test",
        fallback=SimpleNamespace(),
    )
    route = build_device_health_fast_route(application)

    assert run(route(SimpleNamespace(query="turn on the kitchen light"))) is None
    assert application.home_priority_insight is not None


def test_octopus_route_falls_through_for_unrelated_query():
    application = SimpleNamespace(VERSION="test")
    route = build_control_focus_octopus_energy(application)

    assert run(route(SimpleNamespace(query="what is the hallway temperature"))) is None
    assert application.octopus_live_meter_summary is not None
