from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from automation_recommendation import (  # noqa: E402
    AutomationRecommendationService,
    _AUTOMATION_RECOMMENDATION_QUERY,
    install_automation_recommendation_terminal_route,
)


class FakeIndex:
    def __init__(self, devices: list[dict[str, Any]]) -> None:
        self.devices = devices
        self.forced: list[bool] = []

    async def enriched_devices(self, *, force: bool = False):
        self.forced.append(force)
        return list(self.devices)

    @staticmethod
    def _groups(item: dict[str, Any]):
        return set(item.get("test_groups") or [])


class FakeOllama:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.num_ctx = 2048
        self.calls: list[dict[str, Any]] = []

    async def health(self):
        return {
            "online": True,
            "models": ["qwen3.5:4b"],
            "model_present": True,
        }

    def _resolve_routine_model(self, installed: list[str]) -> str:
        return "qwen3.5:4b"

    async def _chat(self, **kwargs: Any):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("test synthesis failure")
        return {
            "message": {
                "content": (
                    "### Washing machine finished alert\n"
                    "Use WashingM power to detect the cycle, then notify the phone when "
                    "power remains low. Arm it only after power first rises above the "
                    "running threshold."
                )
            },
            "_homebrain_model_used": "qwen3.5:4b",
            "_homebrain_provider": "Local Ollama fallback",
        }


def _service(devices: list[dict[str, Any]], *, fail: bool = False):
    ollama = FakeOllama(fail=fail)
    application = SimpleNamespace(ollama=ollama)
    index = FakeIndex(devices)
    service = AutomationRecommendationService(
        application,
        index,
        ai_timeout_seconds=10,
    )
    return service, index, ollama


def test_screenshot_query_matches_bounded_recommendation_route():
    assert _AUTOMATION_RECOMMENDATION_QUERY.match(
        "Suggest one useful automation for the devices I have"
    )
    assert AutomationRecommendationService.matches(
        "Recommend a practical automation using the devices I have."
    )
    assert AutomationRecommendationService.matches(
        "What automation should I create?"
    )
    assert AutomationRecommendationService.matches(
        "Suggest one useful automation for the devices I have and write a rule"
    )
    assert AutomationRecommendationService.matches(
        "Recommend an automation using the devices I have and build the rule."
    )


def test_terminal_route_bypasses_outer_planner_and_remembers_rule_workflow():
    planner_calls = []
    remembered = []

    async def outer_planner(request):
        planner_calls.append(request.query)
        return {"route": "ollama+mcp", "message": "Planner should not run"}

    class Recommendation:
        matches = staticmethod(AutomationRecommendationService.matches)

        async def answer(self, query):
            return {
                "route": "mcp-automation-recommendation",
                "message": "Use Hallway Motion with Hallway Light.",
                "recommendation": {"title": "Hallway motion lighting"},
            }

    class Workflow:
        async def remember_answer(self, session_id, answer):
            remembered.append((session_id, answer["recommendation"]["title"]))

    application = SimpleNamespace(
        ask=outer_planner,
        VERSION="test-version",
        automation_rule_workflow=Workflow(),
    )
    install_automation_recommendation_terminal_route(application, Recommendation())

    request = SimpleNamespace(
        query="Suggest one useful automation for the devices I have",
        session_id="browser-1",
    )
    answer = asyncio.run(application.ask(request))

    assert answer["route"] == "mcp-automation-recommendation"
    assert planner_calls == []
    assert remembered == [("browser-1", "Hallway motion lighting")]


def test_washing_power_candidate_is_preferred_and_ai_uses_verified_evidence():
    service, index, ollama = _service(
        [
            {
                "id": "1",
                "label": "WashingM",
                "room": "Kitchen",
                "test_groups": ["switch", "power", "energy"],
                "currentStates": {"switch": "on", "power": 43.2},
            },
            {
                "id": "2",
                "label": "Kitchen Motion",
                "room": "Kitchen",
                "test_groups": ["motion"],
                "currentStates": {"motion": "inactive"},
            },
            {
                "id": "3",
                "label": "Kitchen Light",
                "room": "Kitchen",
                "test_groups": ["switch", "light"],
                "currentStates": {"switch": "off"},
            },
        ]
    )

    answer = asyncio.run(
        service.answer("Suggest one useful automation for the devices I have")
    )

    assert index.forced == [True]
    assert answer["success"] is True
    assert answer["intent"] == "automation-recommendation"
    assert answer["recommendation"]["type"] == "washing-complete"
    assert answer["recommendation"]["devices"] == ["WashingM"]
    assert answer["ai_used"] is True
    assert answer["model"] == "qwen3.5:4b"
    assert answer["ai_provider"] == "Local Ollama fallback"
    assert len(ollama.calls) == 1
    prompt = str(ollama.calls[0]["messages"][-1]["content"])
    assert "WashingM" in prompt
    assert "above 10 W" in prompt
    assert "below 5 W" in prompt


def test_ai_failure_returns_grounded_recommendation_not_unsupported_error():
    service, _, _ = _service(
        [
            {
                "id": "4",
                "label": "Fridge Door",
                "room": "Kitchen",
                "test_groups": ["contact", "battery"],
                "currentStates": {"contact": "closed", "battery": 17},
            }
        ],
        fail=True,
    )

    answer = asyncio.run(
        service.answer("Suggest one useful automation for the devices I have")
    )

    assert answer["success"] is True
    assert answer["route"] == "mcp-automation-recommendation-ai-fallback"
    assert answer["ai_attempted"] is True
    assert answer["ai_used"] is False
    assert answer["recommendation"]["type"] == "cold-storage-door"
    assert "Fridge Door" in answer["message"]
    assert "remains open for 2 minutes" in answer["message"]
    assert "does not support this question" not in answer["message"]


def test_same_room_motion_and_light_become_a_safe_candidate():
    service, _, _ = _service(
        [
            {
                "id": "5",
                "label": "Hallway Motion",
                "room": "Hallway",
                "test_groups": ["motion"],
                "currentStates": {"motion": "active"},
            },
            {
                "id": "6",
                "label": "Hallway Light",
                "room": "Hallway",
                "test_groups": ["switch", "light"],
                "currentStates": {"switch": "off"},
            },
        ],
        fail=True,
    )

    answer = asyncio.run(
        service.answer("Recommend one automation using the devices I have")
    )

    recommendation = answer["recommendation"]
    assert recommendation["type"] == "motion-lighting"
    assert recommendation["room"] == "Hallway"
    assert recommendation["devices"] == ["Hallway Motion", "Hallway Light"]
    assert "3 minutes with no motion" in recommendation["action"]


def test_release_metadata_is_0421():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (
        ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"
    ).read_text(encoding="utf-8")

    assert "version: '0.4.21-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.21-alpha"' in entrypoint
    assert "install_automation_recommendation" in entrypoint
    assert "install_washing_rule_machine_workflow" in entrypoint
