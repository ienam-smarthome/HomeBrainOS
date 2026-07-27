from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "runtime_route_bridge.py"
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_runtime_bridge_does_not_reinstall_legacy_thermostat_wrapper():
    source = BRIDGE.read_text(encoding="utf-8")

    assert "install_thermostat_summary_guard" not in source
    assert "runtime_thermostat_summary_guard" not in source
    assert source.count("install_cancellable_ask(application)") == 1
    ast.parse(source)


def test_runtime_bridge_follows_declared_thermostat_registry_wiring():
    entrypoint = ENTRYPOINT.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")

    assert 'register_terminal_route(\n    "thermostat-live-state",' in entrypoint
    assert 'register_guard(\n    "thermostat-summary",' in entrypoint
    assert entrypoint.index("thermostat-guard-registry") < entrypoint.index("runtime-route-bridge")
    assert "already installed thermostat semantics through" in bridge
