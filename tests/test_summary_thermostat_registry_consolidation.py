from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_thermostat_terminal_and_summary_guards_share_one_registry():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "summary_thermostat_registry = AnswerGuardRegistry(_core.application)" in source
    terminal = source.index(
        'summary_thermostat_registry.register_terminal_route(\n    "thermostat-live-state"'
    )
    home_guard = source.index(
        'summary_thermostat_registry.register_guard(\n    "home-summary-consistency"'
    )
    thermostat_guard = source.index(
        'summary_thermostat_registry.register_guard(\n    "thermostat-summary"'
    )
    install = source.index(
        '"summary-thermostat-registry",\n    summary_thermostat_registry.install,'
    )

    assert terminal < home_guard < thermostat_guard < install
    assert source.count("summary_thermostat_registry.install") == 1


def test_separate_home_summary_and_thermostat_wrappers_are_removed():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "home_summary_guard_registry =" not in source
    assert "thermostat_guard_registry =" not in source
    assert '"home-summary-guard-registry"' not in source
    assert '"thermostat-guard-registry"' not in source


def test_consolidated_registry_keeps_original_neighbours_and_runtime_setup():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert source.index("semantic-home-registry") < source.index("summary-thermostat-registry")
    assert source.index("summary-thermostat-registry") < source.index("read-terminal-registry")
    assert source.index("auxiliary_request_layers.finalize()") < source.index(
        "install_runtime_route_bridge(_core.application)"
    )
