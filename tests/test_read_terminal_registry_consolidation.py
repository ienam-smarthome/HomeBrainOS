from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_named_rule_status_precedes_climate_extrema_in_one_registry():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "read_terminal_registry = AnswerGuardRegistry(_core.application)" in source
    named_rule = source.index(
        'read_terminal_registry.register_terminal_route(\n    "named-rule-status"'
    )
    climate = source.index(
        'read_terminal_registry.register_terminal_route(\n    "climate-metric-extrema"'
    )
    install = source.index(
        '"read-terminal-registry",\n    read_terminal_registry.install,'
    )

    assert named_rule < climate < install
    assert source.count("read_terminal_registry.install") == 1


def test_legacy_separate_registry_wrappers_are_removed():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "climate_extrema_registry =" not in source
    assert "named_rule_status_registry =" not in source
    assert '"climate-extrema-registry"' not in source
    assert '"named-rule-status-registry"' not in source


def test_consolidated_registry_keeps_original_neighbours():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert source.index("thermostat-guard-registry") < source.index("read-terminal-registry")
    assert source.index("read-terminal-registry") < source.index("answer-guard-registry")
    assert source.index("auxiliary_request_layers.finalize()") < source.index(
        "install_runtime_route_bridge(_core.application)"
    )
