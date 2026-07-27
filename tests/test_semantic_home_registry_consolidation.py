from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_semantic_home_routes_share_one_registry_in_original_order():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "semantic_home_registry = AnswerGuardRegistry(_core.application)" in source
    summary_registration = source.index(
        'semantic_home_registry.register_terminal_route(\n    "semantic-home-summary"'
    )
    query_registration = source.index(
        'semantic_home_registry.register_terminal_route(\n    "semantic-home-query"'
    )
    installation = source.index(
        '"semantic-home-registry",\n    semantic_home_registry.install,'
    )

    assert summary_registration < query_registration < installation
    assert source.count("semantic_home_registry.install") == 1
    assert '"semantic-home-summary",\n    lambda: install_semantic_home_summary_agent' not in source
    assert '"semantic-home-query-registry"' not in source


def test_semantic_home_registry_remains_between_hub_health_and_summary_guard():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert source.index("hub-health-display-registry") < source.index("semantic-home-registry")
    assert source.index("semantic-home-registry") < source.index("home-summary-guard-registry")


def test_runtime_bridge_stays_outside_ask_composition_capture():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "auxiliary_request_handler = auxiliary_request_layers.finalize()" in source
    assert "runtime_request_registry = install_runtime_route_bridge(_core.application)" in source
    assert source.index("auxiliary_request_layers.finalize()") < source.index(
        "install_runtime_route_bridge(_core.application)"
    )
    assert 'capture(\n    "runtime-route-bridge"' not in source
