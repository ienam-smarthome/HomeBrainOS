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

from control_agent_combined_level import install_combined_level_intent  # noqa: E402
from control_agent_goal_based import is_goal_based_control  # noqa: E402
from control_agent_intent import ControlIntentInterpreter  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class GoalHTTP:
    def __init__(self) -> None:
        self.models: list[str] = []
        self.requests: list[dict[str, Any]] = []

    async def post(self, _url: str, *, json: dict[str, Any], timeout: float):
        del timeout
        self.models.append(str(json.get("model") or ""))
        self.requests.append(json)
        assert json.get("tools") is None
        assert "TV/movie 30" in json["messages"][0]["content"]
        content = {
            "intent": "device_control",
            "actions": [
                {
                    "command": "set_level",
                    "value": 30,
                    "target": {
                        "name_hint": "Livingroom Light 1",
                        "room_hint": "Living Room",
                        "device_type": "light",
                        "ordinal": 1,
                        "quantifier": "one",
                        "reference": "none",
                        "exclusions": [],
                    },
                }
            ],
            # Even if a model is overconfident, the goal layer must force confirmation.
            "confidence": 0.97,
        }
        return FakeResponse({"message": {"content": json_module.dumps(content)}})


json_module = json


class GoalApplication:
    OPTIONS = {
        "control_agent_cloud_timeout_seconds": 9,
        "ollama_cloud_timeout_seconds": 12,
    }

    def __init__(self) -> None:
        self.http = GoalHTTP()
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
        if name in {
            "control_agent_cloud_fallback_enabled",
            "control_agent_goal_prefer_cloud",
            "ollama_enabled",
        }:
            return True
        return default


def test_subjective_lighting_goal_is_recognised_but_explicit_levels_are_not():
    assert is_goal_based_control(
        "Make Livingroom Light 1 comfortable for watching TV."
    ) is True
    assert is_goal_based_control("Set Livingroom Light 1 to 30%") is False
    assert is_goal_based_control("Make the fan comfortable") is False


def test_goal_control_uses_strong_cloud_first_and_returns_confirmable_level():
    install_combined_level_intent()
    application = GoalApplication()
    interpreter = ControlIntentInterpreter(application, timeout_seconds=2)

    intent, details = asyncio.run(
        interpreter._interpret_with_ai(
            "Make Livingroom Light 1 comfortable for watching TV.",
            history=[],
            context={},
            inventory=(
                "Livingroom Light 1 | Living Room | device,light\n"
                "Livingroom Light 2 | Living Room | device,light"
            ),
        )
    )

    assert application.http.models == ["gemma4:31b-cloud"]
    assert intent is not None
    assert intent.interpreter == "goal-based-ai-control-intent"
    assert intent.model == "gemma4:31b-cloud"
    assert intent.actions[0].command == "set_level"
    assert intent.actions[0].value == 30
    assert intent.actions[0].target.name_hint == "Livingroom Light 1"
    assert intent.confidence == 0.78
    assert details["goal_based"] is True
    assert details["proposed_level"] == 30
    assert details["ai_provider"] == "Ollama Cloud structured control interpreter"


def test_goal_control_wiring_prevents_general_agent_fallthrough():
    source = (APP_DIR / "control_agent_goal_based.py").read_text(encoding="utf-8")
    combined = (APP_DIR / "control_agent_combined_level.py").read_text(encoding="utf-8")

    assert "safe_fallback" in source
    assert "was not passed to the general answer agent" in source
    assert "install_goal_based_control()" in combined
