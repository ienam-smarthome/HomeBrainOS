from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_runtime_route_bridge_runs_after_ask_composition_finalizes():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert '"runtime-route-bridge"' not in source
    assert "auxiliary_request_handler = auxiliary_request_layers.finalize()" in source
    assert "runtime_request_registry = install_runtime_route_bridge(_core.application)" in source
    assert source.index("auxiliary_request_layers.finalize()") < source.index(
        "install_runtime_route_bridge(_core.application)"
    )
