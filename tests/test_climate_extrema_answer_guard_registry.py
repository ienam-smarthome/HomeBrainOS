from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from answer_guard_registry import AnswerGuardRegistry
from climate_metric_extrema_route import build_climate_metric_extrema_route


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def run(coro):
    return asyncio.run(coro)


class _Router:
    @staticmethod
    def _device_rows(data):
        return list(data)


class _Executor:
    def __init__(self, readings):
        self.router = _Router()
        self._readings = readings

    async def _fresh_capability_result(self, spec):
        return SimpleNamespace(data=self._readings)

    def _measurement_rows(self, rows, spec):
        return rows


def test_climate_extrema_terminal_route_answers_highest_room_humidity():
    executor = _Executor(
        [
            {"label": "Hallway Meter", "room": "Hallway", "value": 52},
            {"label": "Bathroom Meter", "room": "Bathroom", "value": 68},
            {"label": "Fridge Meter", "room": "Kitchen", "value": 90},
        ]
    )
    route = build_climate_metric_extrema_route(executor)

    answer = run(route(SimpleNamespace(query="Which room has the highest humidity?")))

    assert answer is not None
    assert answer["success"] is True
    assert answer["intent"] == "climate-humidity-extreme"
    assert answer["reading"]["room"] == "Bathroom"
    assert answer["reading"]["device"] == "Bathroom Meter"


def test_climate_extrema_terminal_route_delegates_for_unmatched_query():
    route = build_climate_metric_extrema_route(_Executor([]))

    answer = run(route(SimpleNamespace(query="What is the hallway humidity?")))

    assert answer is None


def test_registry_stops_after_climate_extrema_terminal_answer():
    calls = []

    async def base(request):
        calls.append("base")
        return {"message": "fallback"}

    executor = _Executor(
        [{"label": "Bedroom Meter", "room": "Bedroom", "value": 18.5}]
    )
    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)
    registry.register_terminal_route(
        "climate-metric-extrema",
        build_climate_metric_extrema_route(executor),
    )
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="Which room is coldest?")))

    assert answer["intent"] == "climate-temperature-extreme"
    assert calls == []


def test_public_entrypoint_uses_climate_extrema_in_final_read_registry():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "from climate_metric_extrema_route import build_climate_metric_extrema_route" in source
    assert 'read_execution_registry.register_terminal_route(\n    "climate-metric-extrema",' in source
    assert '"read-execution-registry",\n    read_execution_registry.install,' in source
    assert "install_climate_metric_extrema_route" not in source
    assert source.index('"named-rule-status"') < source.index('"climate-metric-extrema"')
    assert source.index('"climate-metric-extrema"') < source.index('"execution-contract"')
