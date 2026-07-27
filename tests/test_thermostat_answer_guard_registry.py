from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import thermostat_summary_registry as registry_module
from answer_guard_registry import AnswerGuardRegistry
from thermostat_summary_registry import (
    build_thermostat_summary_guard,
    build_thermostat_terminal_route,
)


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def run(coro):
    return asyncio.run(coro)


def test_direct_thermostat_query_is_terminal_before_delegation(monkeypatch):
    calls = []

    async def fake_read(application):
        calls.append("read")
        return (
            {
                "label": "Thermostat",
                "temperature": 21.0,
                "heating_setpoint": 19.0,
                "cooling_setpoint": None,
            },
            {"tools_used": []},
        )

    async def base(request):
        calls.append("base")
        return {"message": "base"}

    monkeypatch.setattr(registry_module, "_live_thermostat_reading", fake_read)
    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)
    registry.register_terminal_route(
        "thermostat-live-state",
        build_thermostat_terminal_route(app),
    )
    registry.register_guard(
        "thermostat-summary",
        build_thermostat_summary_guard(app),
    )
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="What is the thermostat setpoint?")))

    assert calls == ["read"]
    assert answer["route"] == "mcp-thermostat-live-state"
    assert "21°C" in answer["message"]
    assert "19°C" in answer["message"]


def test_summary_guard_runs_after_delegation_and_preserves_evidence(monkeypatch):
    calls = []

    async def fake_read(application):
        calls.append("read")
        return (
            {
                "label": "Thermostat",
                "temperature": 25.0,
                "heating_setpoint": 20.0,
                "cooling_setpoint": None,
            },
            {"source": "test", "tools_used": []},
        )

    async def base(request):
        calls.append("base")
        return {
            "message": "The thermostat is set to 25°C.",
            "display": {"summary": "The thermostat is set to 25°C."},
        }

    monkeypatch.setattr(registry_module, "_live_thermostat_reading", fake_read)
    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)
    registry.register_terminal_route(
        "thermostat-live-state",
        build_thermostat_terminal_route(app),
    )
    registry.register_guard(
        "thermostat-summary",
        build_thermostat_summary_guard(app),
    )
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="What's happening at home?")))

    assert calls == ["base", "read"]
    assert answer["thermostat_semantics_corrected"] is True
    assert "room temperature is 25°C" in answer["message"]
    assert "heating setpoint is 20°C" in answer["message"]
    assert answer["display"]["summary"] == answer["message"]
    assert answer["thermostat_summary_guard_read"]["source"] == "test"


def test_public_entrypoint_preserves_thermostat_registry_position():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    home_position = source.index('"home-summary-guard-registry"')
    thermostat_position = source.index('"thermostat-guard-registry"')
    climate_position = source.index('"climate-metric-extrema"')

    assert home_position < thermostat_position < climate_position
    assert 'register_terminal_route(\n    "thermostat-live-state"' in source
    assert 'register_guard(\n    "thermostat-summary"' in source
    assert "install_thermostat_summary_guard" not in source
