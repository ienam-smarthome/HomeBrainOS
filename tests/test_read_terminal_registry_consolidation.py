from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_named_rule_status_and_climate_extrema_share_read_execution_registry():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "read_execution_registry = AnswerGuardRegistry(_core.application)" in source
    named_rule = source.index(
        'read_execution_registry.register_terminal_route(\n    "named-rule-status"'
    )
    climate = source.index(
        'read_execution_registry.register_terminal_route(\n    "climate-metric-extrema"'
    )
    execution_guard = source.index(
        'read_execution_registry.register_guard(\n    "execution-contract"'
    )
    install = source.index(
        '"read-execution-registry",\n    read_execution_registry.install,'
    )

    assert named_rule < climate < execution_guard < install
    assert source.count("read_execution_registry.install") == 1


def test_legacy_separate_read_and_execution_wrappers_are_removed():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "read_terminal_registry =" not in source
    assert "answer_guard_registry =" not in source
    assert '"read-terminal-registry"' not in source
    assert '"answer-guard-registry"' not in source
    assert "climate_extrema_registry =" not in source
    assert "named_rule_status_registry =" not in source


def test_consolidated_registry_keeps_final_neighbours():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert source.index("summary-thermostat-registry") < source.index("read-execution-registry")
    assert source.index("read-execution-registry") < source.index(
        "auxiliary_request_layers.finalize()"
    )
    assert source.index("auxiliary_request_layers.finalize()") < source.index(
        "install_runtime_route_bridge(_core.application)"
    )
