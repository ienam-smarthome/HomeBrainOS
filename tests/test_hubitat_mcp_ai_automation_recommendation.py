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
        "Recommend a practical automation using my devices."
    )
    assert AutomationRecommendationService.matches(
        "What automation should I create?"
    )


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

    answer = asyncio.run(service.answer("Recommend one automation using my devices"))

    recommendation = answer["recommendation"]
    assert recommendation["type"] == "motion-lighting"
    assert recommendation["room"] == "Hallway"
    assert recommendation["devices"] == ["Hallway Motion", "Hallway Light"]
    assert "3 minutes with no motion" in recommendation["action"]


def test_release_metadata_is_0414():
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")
    entrypoint = (
        ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"
    ).read_text(encoding="utf-8")

    assert "version: '0.4.14-alpha'" in config
    assert 'RELEASE_VERSION = "0.4.14-alpha"' in entrypoint
    assert "install_automation_recommendation" in entrypoint
