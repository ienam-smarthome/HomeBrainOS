from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_semantic_home_summary_uses_registry_and_runtime_bridge_stays_direct():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert (
        "from semantic_home_summary_registry import "
        "build_semantic_home_summary_terminal_route"
    ) in source
    assert "install_semantic_home_summary_agent" not in source
    assert 'register_terminal_route(\n    "semantic-home-summary",' in source
    assert '"semantic-home-summary-registry",\n    semantic_home_summary_registry.install,' in source
    assert source.index("semantic-home-summary-registry") < source.index(
        "semantic-home-query-registry"
    )
    assert "auxiliary_request_handler = auxiliary_request_layers.finalize()" in source
    assert "runtime_request_registry = install_runtime_route_bridge(_core.application)" in source
    assert 'capture(\n    "runtime-route-bridge"' not in source
