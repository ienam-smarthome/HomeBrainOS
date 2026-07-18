from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_webui import patch_page  # noqa: E402
from motion_light_insight import MotionLightInsightService  # noqa: E402
from ollama_agent_adaptive import AdaptiveFinalAnswerAgent  # noqa: E402
from ollama_agent_fast import OllamaUnavailable  # noqa: E402
from ollama_agent_final_answer import FinalAnswerNaturalAgent  # noqa: E402
from webui import render_page  # noqa: E402


def make_agent() -> AdaptiveFinalAnswerAgent:
    agent = object.__new__(AdaptiveFinalAnswerAgent)
    agent.model = "gemma4:31b-cloud"
    agent.cloud_enabled = True
    agent.cloud_model = "gemma4:31b-cloud"
    agent.local_fallback_model = "qwen3.5:4b"
    agent.cloud_fallback_local = True
    agent.cloud_timeout_seconds = 25.0
    agent._cloud_present_hint = True
    return agent


def test_cloud_chat_uses_cloud_when_available(monkeypatch):
    calls: list[str] = []

    async def fake_chat(self, **kwargs: Any):
        calls.append(kwargs["model"])
        return {"message": {"content": "Cloud answer"}}

    monkeypatch.setattr(FinalAnswerNaturalAgent, "_chat", fake_chat)
    agent = make_agent()

    body = asyncio.run(
        agent._chat(
            model="gemma4:31b-cloud",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            timeout_seconds=20,
            num_ctx=2048,
            num_predict=100,
            temperature=0.1,
        )
    )

    assert calls == ["gemma4:31b-cloud"]
    assert body["_homebrain_model_used"] == "gemma4:31b-cloud"
    assert body["_homebrain_provider"] == "Ollama Cloud"


def test_cloud_failure_retries_local_qwen(monkeypatch):
    calls: list[str] = []

    async def fake_chat(self, **kwargs: Any):
        model = kwargs["model"]
        calls.append(model)
        if model == "gemma4:31b-cloud":
            raise OllamaUnavailable("free cloud usage temporarily unavailable")
        return {"message": {"content": "Local answer"}}

    monkeypatch.setattr(FinalAnswerNaturalAgent, "_chat", fake_chat)
    agent = make_agent()

    body = asyncio.run(
        agent._chat(
            model="gemma4:31b-cloud",
            messages=[{"role": "user", "content": "Hello"}],
            tools=None,
            timeout_seconds=20,
            num_ctx=2048,
            num_predict=100,
            temperature=0.1,
        )
    )

    assert calls == ["gemma4:31b-cloud", "qwen3.5:4b"]
    assert body["_homebrain_model_used"] == "qwen3.5:4b"
    assert body["_homebrain_provider"] == "Local Ollama fallback"
    assert "temporarily unavailable" in body["_homebrain_cloud_error"]


class MotionIndex:
    async def enriched_devices(self, *, force: bool = False):
        return [
            {
                "id": "1",
                "label": "Bedroom 2 FP1",
                "room": "Bedroom 2",
                "currentStates": {"motion": "active"},
            },
            {
                "id": "2",
                "label": "Bedroom 2 Light",
                "room": "Bedroom 2",
                "currentStates": {"switch": "off"},
            },
            {
                "id": "3",
                "label": "Bedroom 3 Presence Sensor",
                "room": "Bedroom 3",
                "currentStates": {"motion": "active"},
            },
            {
                "id": "4",
                "label": "Bedroom 3 Light",
                "room": "Bedroom 3",
                "currentStates": {"switch": "on"},
            },
            {
                "id": "5",
                "label": "Hallway Light",
                "room": "Hallway",
                "currentStates": {"switch": "off"},
            },
        ]

    @staticmethod
    def _groups(item: dict[str, Any]) -> set[str]:
        label = str(item.get("label") or "").lower()
        attrs = item.get("currentStates") or {}
        groups = set()
        if "motion" in attrs:
            groups.add("motion")
        if "switch" in attrs:
            groups.add("light" if "light" in label else "switch")
        return groups


class CloudOllama:
    model = "gemma4:31b-cloud"
    num_ctx = 2048

    async def health(self):
        return {
            "online": True,
            "models": ["gemma4:31b-cloud", "qwen3.5:4b"],
        }

    def _resolve_routine_model(self, installed: list[str]) -> str:
        return "gemma4:31b-cloud"

    async def _chat(self, **kwargs: Any):
        return {
            "message": {
                "content": (
                    "Motion is active in Bedroom 2 and Bedroom 3. Bedroom 2 Light "
                    "is off in an active room; Bedroom 3 has no nearby light off."
                )
            },
            "_homebrain_model_used": "gemma4:31b-cloud",
            "_homebrain_provider": "Ollama Cloud",
        }


def test_motion_light_route_uses_same_room_only_and_cloud_writes_answer():
    app = SimpleNamespace(
        ollama=CloudOllama(),
        OPTIONS={"ollama_cloud_model": "gemma4:31b-cloud"},
    )
    service = MotionLightInsightService(app, MotionIndex(), ai_timeout_seconds=20)

    answer = asyncio.run(
        service.answer(
            "Find active motion and tell me which nearby lights are off."
        )
    )

    assert answer["route"] == "ollama+motion-light-insight"
    assert answer["ai_provider"] == "Ollama Cloud"
    assert len(answer["active_motion"]) == 2
    assert answer["nearby_off_lights"] == [
        {"room": "Bedroom 2", "lights_off": ["Bedroom 2 Light"]},
        {"room": "Bedroom 3", "lights_off": []},
    ]
    assert "Hallway Light" not in answer["message"]
    assert answer["display"]["metrics"][2]["value"] == "1"


def test_webui_displays_ai_provider_badge():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.13-alpha"))

    assert "if(answer.ai_provider)" in page
    assert "Ollama Cloud" not in page or "ai_provider" in page
    assert "mcp-motion-light-state-unavailable" not in page or "routeLabel" in page
