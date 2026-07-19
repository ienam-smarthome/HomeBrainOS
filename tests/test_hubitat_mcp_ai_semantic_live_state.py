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
from semantic_metric_comparison_live import (  # noqa: E402
    SemanticMetricComparisonExecutor,
)
from semantic_read_intent import SemanticReadIntent  # noqa: E402


def result(data: Any, *, error: bool = False, text: str = "") -> MCPToolResult:
    return MCPToolResult(
        name="hub_list_devices",
        arguments={},
        raw={"isError": error},
        text=text,
        data=data,
        is_error=error,
    )


class LiveStateClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.invalidations: list[str] = []

    async def invalidate(self, category: str) -> int:
        self.invalidations.append(category)
        return 1

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        assert name == "hub_list_devices"
        args = dict(arguments or {})
        self.calls.append(args)
        capability = args.get("capabilityFilter")
        detailed = bool(args.get("detailed"))

        if capability == "Power Meter" and detailed:
            # Real MCP variants can return the attribute definition without its
            # current value in detailed mode.
            return result(
                {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Fridge",
                            "room": "Appliances",
                            "attributes": [
                                {"name": "power", "dataType": "NUMBER", "unit": "W"}
                            ],
                        },
                        {
                            "id": "2",
                            "label": "Computer",
                            "room": "Multimedia",
                            "attributes": [
                                {"name": "power", "dataType": "NUMBER", "unit": "W"}
                            ],
                        },
                    ]
                }
            )
        if capability == "Power Meter" and not detailed:
            return result(
                {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Fridge",
                            "room": "Appliances",
                            "currentStates": {"power": {"value": 89, "unit": "W"}},
                        },
                        {
                            "id": "2",
                            "label": "Computer",
                            "room": "Multimedia",
                            "currentStates": {"power": "34 W"},
                        },
                    ]
                }
            )
        raise AssertionError(args)


class CompactCapabilityClient(LiveStateClient):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        assert name == "hub_list_devices"
        args = dict(arguments or {})
        self.calls.append(args)
        capability = args.get("capabilityFilter")
        detailed = bool(args.get("detailed"))
        if capability == "Power Meter":
            return result({"devices": []})
        if capability == "PowerMeter" and not detailed:
            return result(
                {
                    "devices": [
                        {
                            "id": "7",
                            "label": "Tasmota Freezer",
                            "room": "Appliances",
                            "currentStates": {"power": 72},
                        }
                    ]
                }
            )
        raise AssertionError(args)


class NoValueClient(LiveStateClient):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        assert name == "hub_list_devices"
        args = dict(arguments or {})
        self.calls.append(args)
        if args.get("capabilityFilter") in {"Power Meter", "PowerMeter"}:
            return result(
                {
                    "devices": [
                        {
                            "id": "1",
                            "label": "Fridge",
                            "attributes": [{"name": "power", "unit": "W"}],
                        }
                    ]
                }
            )
        return result({"devices": []})


class Router:
    def __init__(self, client: Any) -> None:
        self.device_index = SimpleNamespace(client=client)
        self.client = client

    @staticmethod
    def _device_rows(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            value = value.get("devices") or []
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    @staticmethod
    def _room_name(item: dict[str, Any]) -> str:
        return str(item.get("room") or "")

    @staticmethod
    def _response(
        message: str,
        intent: str,
        success: bool,
        source: MCPToolResult,
    ) -> dict[str, Any]:
        return {
            "message": message,
            "intent": intent,
            "success": success,
            "source": source.data,
        }


def power_intent() -> SemanticReadIntent:
    return SemanticReadIntent(
        intent="metric_comparison",
        metric="power",
        operation="max",
        group_by="device",
        scope_kind="all",
        scope_name="",
        entity_names=(),
        top_n=3,
        confidence=0.98,
    )


def test_detailed_metadata_is_merged_with_compact_live_current_states():
    client = LiveStateClient()
    executor = SemanticMetricComparisonExecutor(Router(client))

    answer = asyncio.run(executor.execute(power_intent(), query="which device uses most power"))

    assert answer["success"] is True
    assert answer["ranked_entities"][0]["label"] == "Fridge"
    assert answer["ranked_entities"][0]["value"] == 89
    assert answer["ranked_entities"][1]["label"] == "Computer"
    assert answer["ranked_entities"][1]["value"] == 34
    assert "Fridge has the highest current power at 89 W" in answer["message"]
    assert client.invalidations == ["devices"]
    assert [call.get("detailed") for call in client.calls] == [True, False]
    assert "currentStates" in client.calls[0]["fields"]
    assert "attributes" in client.calls[0]["fields"]
    assert "currentStates" in client.calls[1]["fields"]
    assert answer["source"]["evidenceSources"] == [
        "detailed-currentStates+attributes",
        "summary-currentStates",
    ]


def test_no_space_capability_alias_recovers_custom_power_meter_driver():
    client = CompactCapabilityClient()
    executor = SemanticMetricComparisonExecutor(Router(client))

    answer = asyncio.run(executor.execute(power_intent(), query="biggest electricity load"))

    assert answer["success"] is True
    assert answer["ranked_entities"][0]["label"] == "Tasmota Freezer"
    assert answer["ranked_entities"][0]["value"] == 72
    assert [call.get("capabilityFilter") for call in client.calls] == [
        "Power Meter",
        "Power Meter",
        "PowerMeter",
    ]


def test_missing_numeric_value_still_returns_unavailable_instead_of_guessing():
    client = NoValueClient()
    router = Router(client)
    router.device_index = None
    executor = SemanticMetricComparisonExecutor(router)

    answer = asyncio.run(executor.execute(power_intent(), query="which device uses most power"))

    assert answer["success"] is False
    assert answer["ranked_entities"] == []
    assert answer["measurement_readings"] == []
    assert "none returned a current numeric current power value" in answer["message"]


def test_release_wires_live_state_semantic_executor():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "from semantic_metric_comparison_live import SemanticMetricComparisonExecutor" in entrypoint
