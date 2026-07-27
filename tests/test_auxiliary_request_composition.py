from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from request_composition import AskCompositionBuilder  # noqa: E402


def test_builder_preserves_installer_results_and_declares_exact_order():
    calls: list[str] = []

    async def base(_request):
        calls.append("core")
        return {"route": "core"}

    application = SimpleNamespace(ask=base)
    builder = AskCompositionBuilder(application)

    def installer(name: str, result: object):
        def install():
            next_handler = application.ask

            async def handler(request):
                calls.append(f"{name}:before")
                answer = await next_handler(request)
                calls.append(f"{name}:after")
                return answer

            application.ask = handler
            return result

        return install

    first_result = object()
    second_result = object()
    assert builder.capture("first", installer("first", first_result)) is first_result
    assert builder.capture("second", installer("second", second_result)) is second_result

    final_handler = builder.finalize()
    answer = asyncio.run(final_handler(SimpleNamespace(query="status")))

    assert answer == {"route": "core"}
    assert calls == [
        "second:before",
        "first:before",
        "core",
        "first:after",
        "second:after",
    ]
    assert final_handler.__homebrain_ask_layers__ == (
        "second",
        "first",
        "core-request-stack",
    )
    assert application.ask is final_handler


def test_builder_rejects_installers_that_do_not_wrap_ask():
    async def base(_request):
        return {"route": "core"}

    application = SimpleNamespace(ask=base)
    builder = AskCompositionBuilder(application)

    with pytest.raises(RuntimeError, match="did not wrap"):
        builder.capture("not-a-layer", lambda: object())


def test_builder_detects_untracked_mutation():
    async def base(_request):
        return {"route": "core"}

    async def untracked(_request):
        return {"route": "untracked"}

    application = SimpleNamespace(ask=base)
    builder = AskCompositionBuilder(application)
    application.ask = untracked

    with pytest.raises(RuntimeError, match="Untracked"):
        builder.finalize()


def test_entrypoint_captures_final_auxiliary_request_wrappers():
    source = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    expected_layers = (
        "named-app-control",
        "hub-health-display-registry",
        "semantic-home-registry",
        "summary-thermostat-registry",
        "read-execution-registry",
    )

    assert "auxiliary_request_layers = AskCompositionBuilder(" in source
    assert source.count("auxiliary_request_layers.capture(") == len(expected_layers)
    assert "auxiliary_request_handler = auxiliary_request_layers.finalize()" in source

    positions = []
    for layer in expected_layers:
        assert f'"{layer}"' in source
        positions.append(source.index(f'"{layer}"'))
    assert positions == sorted(positions)

    finalized = source.index("auxiliary_request_layers.finalize()")
    runtime_bridge = source.index("install_runtime_route_bridge(_core.application)")
    assert finalized < runtime_bridge
    assert 'capture(\n    "runtime-route-bridge"' not in source
