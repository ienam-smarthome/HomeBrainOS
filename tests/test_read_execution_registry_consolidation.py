from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_read_routes_and_execution_guard_share_one_registry():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "read_execution_registry = AnswerGuardRegistry(_core.application)" in source
    named_rule = source.index(
        'read_execution_registry.register_terminal_route(\n    "named-rule-status"'
    )
    climate = source.index(
        'read_execution_registry.register_terminal_route(\n    "climate-metric-extrema"'
    )
    guard = source.index(
        'read_execution_registry.register_guard(\n    "execution-contract"'
    )
    install = source.index(
        '"read-execution-registry",\n    read_execution_registry.install,'
    )

    assert named_rule < climate < guard < install
    assert source.count("read_execution_registry.install") == 1


def test_separate_read_and_execution_wrappers_are_removed():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "read_terminal_registry =" not in source
    assert "answer_guard_registry =" not in source
    assert '"read-terminal-registry"' not in source
    assert '"answer-guard-registry"' not in source


def test_consolidated_registry_keeps_neighbours_and_runtime_setup():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert source.index("summary-thermostat-registry") < source.index("read-execution-registry")
    assert source.index("auxiliary_request_layers.finalize()") < source.index(
        "install_runtime_route_bridge(_core.application)"
    )
