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
from semantic_read_pipeline import install_semantic_read_pipeline  # noqa: E402


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
        if capability == "Power Meter" and detailed:
            raise AssertionError("Detailed mode must not precede a valid compact live read")
        raise AssertionError(args)


class CompactCapabilityClient(LiveStateClient):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        assert name == "hub_list_devices"
        args = dict(arguments or {})
        self.calls.append(args)
        capability = args.get("capabilityFilter")
        detailed = bool(args.get("detailed"))
        if capability == "Power Meter" and not detailed:
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


class RejectedShapeThenAliasClient(CompactCapabilityClient):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        assert name == "hub_list_devices"
        args = dict(arguments or {})
        self.calls.append(args)
        capability = args.get("capabilityFilter")
        detailed = bool(args.get("detailed"))
        if capability == "Power Meter" and not detailed:
            raise RuntimeError("unsupported capability spelling")
        if capability == "PowerMeter" and not detailed:
            return result(
                {
                    "devices": [
                        {
                            "id": "9",
                            "label": "Fridge",
                            "room": "Appliances",
                            "currentStates": {"power": "89 W"},
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


def test_compact_live_current_states_are_the_first_and_sufficient_evidence():
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
    assert len(client.calls) == 1
    assert client.calls[0]["detailed"] is False
    assert client.calls[0]["fields"] == [
        "id",
        "name",
        "label",
        "room",
        "currentStates",
        "disabled",
        "lastActivity",
    ]
    assert answer["source"]["evidenceSources"] == ["summary-currentStates"]


def test_no_space_capability_alias_recovers_custom_power_meter_driver():
    client = CompactCapabilityClient()
    executor = SemanticMetricComparisonExecutor(Router(client))

    answer = asyncio.run(executor.execute(power_intent(), query="biggest electricity load"))

    assert answer["success"] is True
    assert answer["ranked_entities"][0]["label"] == "Tasmota Freezer"
    assert answer["ranked_entities"][0]["value"] == 72
    assert [call.get("capabilityFilter") for call in client.calls] == [
        "Power Meter",
        "PowerMeter",
    ]


def test_one_rejected_request_shape_does_not_abort_the_compatible_alias_read():
    client = RejectedShapeThenAliasClient()
    executor = SemanticMetricComparisonExecutor(Router(client))

    answer = asyncio.run(executor.execute(power_intent(), query="which device uses most power"))

    assert answer["success"] is True
    assert answer["ranked_entities"][0]["value"] == 89
    assert "unsupported capability spelling" in " ".join(answer["source"]["evidenceErrors"])
    assert [call.get("capabilityFilter") for call in client.calls] == [
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


def test_executor_exception_is_reported_without_calling_cloud_planner():
    cloud_calls = 0

    async def original_ask(_request: Any) -> dict[str, Any]:
        nonlocal cloud_calls
        cloud_calls += 1
        return {"success": True, "message": "Cloud guessed a result", "route": "ollama+mcp"}

    class FailingExecutor:
        async def execute(self, _intent: Any, *, query: str = "") -> dict[str, Any]:
            raise RuntimeError("unsupported detailed field")

    application = SimpleNamespace(
        ask=original_ask,
        option_bool=lambda _name, _default=False: True,
    )
    classifier = install_semantic_read_pipeline(application, FailingExecutor())

    async def classify(_query: str, _history: Any):
        return power_intent(), {
            "ai_success": True,
            "ai_model": "qwen3.5:4b",
            "ai_provider": "Local Ollama semantic classifier",
        }

    classifier.classify = classify
    request = SimpleNamespace(
        query="which device is using most power?",
        history=[],
    )

    answer = asyncio.run(application.ask(request))

    assert cloud_calls == 0
    assert answer["success"] is False
    assert answer["route"] == "semantic+mcp"
    assert answer["intent"] == "semantic-power-evidence-error"
    assert answer["semantic_intent_error"] == "unsupported detailed field"
    assert answer["display"]["metrics"][1]["value"] == "Not used"
    assert '"cloud_fallback_blocked": true' in answer["technical"]


def test_release_wires_live_state_semantic_executor():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "from semantic_metric_comparison_live import SemanticMetricComparisonExecutor" in entrypoint
