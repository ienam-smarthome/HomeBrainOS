from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from mcp_client import MCPToolResult  # noqa: E402
from routing_policy import classify_query, is_semantic_read_candidate  # noqa: E402
from semantic_metric_comparison import (  # noqa: E402
    SemanticMetricComparisonExecutor,
    format_measurement,
    measurement_reading,
)
from semantic_read_intent import (  # noqa: E402
    SemanticReadIntent,
    SemanticReadIntentClassifier,
    install_semantic_read_intent,
)


def result(data: Any) -> MCPToolResult:
    return MCPToolResult(
        name="hub_list_devices",
        arguments={},
        raw={},
        text="",
        data=data,
        is_error=False,
    )


def intent(
    metric: str,
    operation: str = "max",
    group_by: str = "device",
    *,
    top_n: int = 3,
) -> SemanticReadIntent:
    return SemanticReadIntent(
        intent="metric_comparison",
        metric=metric,
        operation=operation,
        group_by=group_by,
        scope_kind="all",
        scope_name="",
        entity_names=(),
        top_n=top_n,
        confidence=0.95,
    )


class FakeBroker:
    def __init__(self) -> None:
        self.invalidated: list[str] = []

    async def invalidate(self, category: str) -> int:
        self.invalidated.append(category)
        return 2


class FakeIndex:
    def __init__(self, devices: list[dict[str, Any]]) -> None:
        self.client = FakeBroker()
        self.devices = devices
        self.calls: list[tuple[str, bool, bool]] = []

    async def invalidate(self) -> None:
        return None

    async def capability_result(
        self,
        capability: str,
        *,
        detailed: bool,
        force: bool,
    ) -> MCPToolResult:
        self.calls.append((capability, detailed, force))
        return result({"devices": self.devices})

    async def metadata_result(self, *, force: bool) -> MCPToolResult:
        return result({"devices": self.devices})


class FakeRouter:
    def __init__(self, devices: list[dict[str, Any]]) -> None:
        self.device_index = FakeIndex(devices)

    @staticmethod
    def _device_rows(data: Any) -> list[dict[str, Any]]:
        return list(data.get("devices") or [])

    @staticmethod
    def _room_name(item: dict[str, Any]) -> str:
        return str(item.get("room") or "")

    @staticmethod
    def _response(
        message: str,
        intent_name: str,
        success: bool,
        tool_result: MCPToolResult,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "intent": intent_name,
            "message": message,
            "tools_used": [{"name": tool_result.name, "success": not tool_result.is_error}],
        }


def test_analytical_device_question_routes_to_semantic_read():
    decision = classify_query("Which device is using the most power right now?")

    assert decision.route == "semantic-read"
    assert "AI interprets" in decision.reason
    assert is_semantic_read_candidate("What appliance is the greediest?") is True


def test_controls_never_enter_semantic_read_classifier():
    assert is_semantic_read_candidate("Turn off the device using the most power") is False
    assert classify_query("turn off freezer").route == "mcp-fast"
    assert classify_query("what is the weather?").route == "mcp-fast"


def test_structured_payload_is_strictly_validated():
    parsed = SemanticReadIntentClassifier.validate_payload(
        {
            "intent": "metric_comparison",
            "metric": "power",
            "operation": "max",
            "group_by": "device",
            "scope_kind": "all",
            "scope_name": "",
            "entity_names": [],
            "top_n": 3,
            "confidence": 0.98,
        }
    )

    assert parsed is not None
    assert parsed.metric == "power"
    assert parsed.operation == "max"
    assert SemanticReadIntentClassifier.validate_payload(
        {
            "intent": "metric_comparison",
            "metric": "switch",
            "operation": "max",
            "group_by": "device",
            "scope_kind": "all",
            "scope_name": "",
            "entity_names": [],
            "top_n": 3,
            "confidence": 1,
        }
    ) is None


def test_resilient_fallback_interprets_multiple_metric_wordings():
    power = SemanticReadIntentClassifier._deterministic_fallback(
        "What appliance has the biggest electricity load?"
    )
    cold = SemanticReadIntentClassifier._deterministic_fallback(
        "Which room is coldest?"
    )
    battery = SemanticReadIntentClassifier._deterministic_fallback(
        "Show the lowest battery device"
    )

    assert power is not None and (power.metric, power.operation) == ("power", "max")
    assert cold is not None and (cold.metric, cold.operation, cold.group_by) == (
        "temperature",
        "min",
        "room",
    )
    assert battery is not None and (battery.metric, battery.operation) == (
        "battery",
        "min",
    )


def test_power_executor_uses_detailed_capability_and_separates_whole_home_meter():
    router = FakeRouter(
        [
            {
                "id": "1",
                "label": "Freezer",
                "room": "Appliances",
                "attributes": [
                    {"name": "power", "currentValue": "72", "unit": "W"}
                ],
            },
            {
                "id": "2",
                "label": "Computer",
                "room": "Multimedia",
                "attributes": [
                    {"name": "power", "currentValue": "0.05", "unit": "kW"}
                ],
            },
            {
                "id": "3",
                "label": "Octopus Live Meter Display Power",
                "room": None,
                "attributes": [
                    {"name": "power", "currentValue": "0.41", "unit": "kW"}
                ],
            },
        ]
    )
    executor = SemanticMetricComparisonExecutor(router)

    answer = asyncio.run(executor.execute(intent("power"), query="highest power"))

    assert answer["success"] is True
    assert answer["ranked_entities"][0]["label"] == "Freezer"
    assert answer["ranked_entities"][0]["value"] == 72
    assert "Freezer has the highest current power" in answer["message"]
    assert "whole-home meter is 410 W" in answer["message"]
    assert router.device_index.calls == [("Power Meter", True, True)]
    assert router.device_index.client.invalidated == ["devices"]


def test_room_temperature_comparison_averages_room_sensors():
    router = FakeRouter(
        [
            {
                "id": "1",
                "label": "Bedroom meter",
                "room": "Bedroom",
                "attributes": [{"name": "temperature", "currentValue": 21, "unit": "C"}],
            },
            {
                "id": "2",
                "label": "Bedroom TRV",
                "room": "Bedroom",
                "attributes": [{"name": "temperature", "currentValue": 23, "unit": "C"}],
            },
            {
                "id": "3",
                "label": "Living room meter",
                "room": "Living Room",
                "attributes": [{"name": "temperature", "currentValue": 25, "unit": "C"}],
            },
        ]
    )
    executor = SemanticMetricComparisonExecutor(router)

    answer = asyncio.run(
        executor.execute(intent("temperature", group_by="room"), query="warmest room")
    )

    assert answer["ranked_entities"][0]["label"] == "Living Room"
    bedroom = next(item for item in answer["ranked_entities"] if item["label"] == "Bedroom")
    assert bedroom["value"] == 22
    assert bedroom["source_count"] == 2


def test_measurement_parser_normalises_units_without_mixing_energy_and_power():
    from semantic_metric_comparison import _SPECS  # noqa: PLC0415

    power = measurement_reading(
        {"attributes": [{"name": "power", "currentValue": "1.2", "unit": "kW"}]},
        _SPECS["power"],
    )
    temperature = measurement_reading(
        {"attributes": [{"name": "temperature", "currentValue": "68", "unit": "F"}]},
        _SPECS["temperature"],
    )
    wrong = measurement_reading(
        {"attributes": [{"name": "energy", "currentValue": "15", "unit": "kWh"}]},
        _SPECS["power"],
    )

    assert power == (1200.0, "power")
    assert temperature is not None and round(temperature[0], 1) == 20.0
    assert wrong is None
    assert format_measurement(_SPECS["power"], 1200) == "1.2 kW"


def test_installer_uses_fallback_parser_when_ollama_is_disabled():
    calls: list[str] = []

    async def original(request: Any) -> dict[str, Any]:
        calls.append(request.query)
        return {"success": True, "route": "original", "message": "original"}

    class FakeExecutor:
        async def execute(self, parsed: SemanticReadIntent, *, query: str):
            return {
                "success": True,
                "message": f"{parsed.metric}:{parsed.operation}",
            }

    application = SimpleNamespace(
        ask=original,
        ollama=SimpleNamespace(),
        option_bool=lambda name, default=True: False if name == "ollama_enabled" else default,
    )
    install_semantic_read_intent(application, FakeExecutor())
    request = SimpleNamespace(
        query="Which device has the highest power?",
        history=[],
    )

    answer = asyncio.run(application.ask(request))

    assert answer["route"] == "semantic+mcp"
    assert answer["semantic_intent"]["metric"] == "power"
    assert calls == []


def test_release_installs_semantic_pipeline_not_phrase_specific_power_router():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "install_semantic_read_intent" in entrypoint
    assert "SemanticMetricComparisonExecutor" in entrypoint
    assert "from fast_fallback_multi_control import FastFallbackRouter" in entrypoint
    assert "fast_fallback_power_comparison" not in entrypoint
