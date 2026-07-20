from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

import request_tracing  # noqa: E402
from control_agent_claude_first import (  # noqa: E402
    install_claude_first_control_interpreter,
    is_probable_control_request,
    parse_natural_level,
    percentage_value,
)
from control_agent_combined_level import install_combined_level_intent  # noqa: E402
from control_agent_intent import ControlIntentInterpreter  # noqa: E402


class EmptyApplication:
    ollama = SimpleNamespace()
    OPTIONS: dict[str, Any] = {}

    @staticmethod
    def option_bool(_name: str, default: bool = False) -> bool:
        return default


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class ModelHTTP:
    def __init__(self) -> None:
        self.models: list[str] = []

    async def post(self, _url: str, *, json: dict[str, Any], timeout: float):
        del timeout
        model = str(json.get("model") or "")
        self.models.append(model)
        assert json.get("tools") is None
        assert json.get("format")
        if model == "qwen3.5:4b":
            raise TimeoutError("local intent timed out")
        content = {
            "intent": "device_control",
            "actions": [
                {
                    "command": "set_level",
                    "value": 30,
                    "target": {
                        "name_hint": "Bedroom 1 Light",
                        "room_hint": "Bedroom 1",
                        "device_type": "light",
                        "ordinal": 1,
                        "quantifier": "one",
                        "reference": "none",
                        "exclusions": [],
                    },
                }
            ],
            "confidence": 0.97,
        }
        return FakeResponse({"message": {"content": json_module.dumps(content)}})


# Avoid shadowing the json module in ModelHTTP.post's keyword argument.
json_module = json


class ModelApplication:
    OPTIONS = {
        "control_agent_cloud_timeout_seconds": 9,
        "ollama_cloud_timeout_seconds": 12,
    }

    def __init__(self) -> None:
        self.http = ModelHTTP()
        self.ollama = SimpleNamespace(
            planner_model="qwen3.5:4b",
            local_fallback_model="qwen3.5:4b",
            model="gemma4:31b-cloud",
            cloud_model="gemma4:31b-cloud",
            cloud_enabled=True,
            base_url="http://ollama.test:11434",
            keep_alive="30m",
            _http=self.http,
        )

    @staticmethod
    def option_bool(name: str, default: bool = False) -> bool:
        if name == "control_agent_cloud_fallback_enabled":
            return True
        if name == "ollama_enabled":
            return True
        return default


def test_spoken_percentage_values_are_normalised_safely():
    assert percentage_value("thirty percent") == 30
    assert percentage_value("forty five") == 45
    assert percentage_value("half brightness") == 50
    assert percentage_value("three quarters") == 75
    assert percentage_value("one hundred") == 100
    assert percentage_value("one hundred and one") is None


def test_exact_claude_example_is_a_fast_structured_control():
    intent = parse_natural_level("Put bedroom one light at about thirty percent.")

    assert intent is not None
    assert intent.model is None
    assert intent.interpreter == "deterministic-natural-control-parser"
    assert len(intent.actions) == 1
    action = intent.actions[0]
    assert action.command == "set_level"
    assert action.value == 30
    assert action.target.name_hint == "bedroom one light"


def test_agent_first_triage_recognises_natural_controls_but_not_reads():
    assert is_probable_control_request(
        "Put bedroom one light at about thirty percent."
    ) is True
    assert is_probable_control_request("Bring the floor lamp down to half brightness") is True
    assert is_probable_control_request("Which bedroom light is at thirty percent?") is False
    assert is_probable_control_request("What lights are on?") is False


def test_proven_exact_numeric_parser_remains_unchanged_and_ai_free():
    install_combined_level_intent()
    intent = ControlIntentInterpreter(EmptyApplication())._deterministic_intent(
        "set Bedroom 1 Light at 30%"
    )

    assert intent is not None
    assert intent.interpreter == "deterministic-control-parser"
    assert intent.model is None
    assert intent.actions[0].target.name_hint == "Bedroom 1 Light"
    assert intent.actions[0].value == 30


def test_request_trace_identifies_natural_control_before_read_only_routing():
    install_combined_level_intent()
    decision = request_tracing.classify_query(
        "Put bedroom one light at about thirty percent."
    )

    assert decision.route == "control-agent"
    assert "before read-only routing" in decision.reason


def test_local_interpreter_failure_falls_back_to_strong_cloud_schema_model():
    install_claude_first_control_interpreter()
    application = ModelApplication()
    interpreter = ControlIntentInterpreter(application, timeout_seconds=2)

    intent, details = asyncio.run(
        interpreter._interpret_with_ai(
            "make bedroom one light comfortable",
            history=[],
            context={},
            inventory="Bedroom 1 Light | Bedroom 1 | light, device",
        )
    )

    assert application.http.models == ["qwen3.5:4b", "gemma4:31b-cloud"]
    assert intent is not None
    assert intent.model == "gemma4:31b-cloud"
    assert intent.actions[0].target.name_hint == "Bedroom 1 Light"
    assert intent.actions[0].value == 30
    assert details["ai_provider"] == "Ollama Cloud structured control interpreter"
    assert len(details["model_attempts"]) == 2
    assert details["model_attempts"][0]["error"] == "local intent timed out"
