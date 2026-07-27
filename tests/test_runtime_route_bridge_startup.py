from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def test_runtime_bridge_runs_after_request_stack_finalization():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    finalize = "auxiliary_request_handler = auxiliary_request_layers.finalize()"
    runtime = "runtime_request_registry = install_runtime_route_bridge(_core.application)"

    assert finalize in source
    assert runtime in source
    assert source.index(finalize) < source.index(runtime)
    assert 'auxiliary_request_layers.capture(\n    "runtime-route-bridge"' not in source
