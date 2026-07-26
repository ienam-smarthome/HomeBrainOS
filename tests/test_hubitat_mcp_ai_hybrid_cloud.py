from __future__ import annotations

import asyncio
import pytest
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


class CloudOllama:
    model = "gemma4:31b-cloud"
    num_ctx = 2048

    async def health(self):
        return {
            "online": True,
            "models": [
                "gemma4:31b-cloud",
            ],
        }

    def _resolve_routine_model(self, installed):
        return "gemma4:31b-cloud"

    async def _chat(self, **kwargs):
        return {
            "message": {
                "content": (
                    "Bedroom 2 Motion is active. "
                    "Bedroom 2 Light is off."
                )
            },
            "_homebrain_model_used": "gemma4:31b-cloud",
            "_homebrain_provider": "Ollama Cloud",
        }




class MotionIndex:
    async def enriched_devices(self, force: bool = False):
        return [
            {
                "label": "Bedroom 2 Motion",
                "name": "Bedroom 2 Motion",
                "room": "Bedroom 2",
                "roomName": "Bedroom 2",
                "deviceType": "motionSensor",
                "attributes": {"motion": "active"},
            },
            {
                "label": "Bedroom 3 Motion",
                "name": "Bedroom 3 Motion",
                "room": "Bedroom 3",
                "roomName": "Bedroom 3",
                "deviceType": "motionSensor",
                "attributes": {"motion": "active"},
            },
            {
                "label": "Bedroom 2 Light",
                "name": "Bedroom 2 Light",
                "room": "Bedroom 2",
                "roomName": "Bedroom 2",
                "deviceType": "switch",
                "attributes": {"switch": "off"},
            },
            {
                "label": "Bedroom 3 Light",
                "name": "Bedroom 3 Light",
                "room": "Bedroom 3",
                "roomName": "Bedroom 3",
                "deviceType": "switch",
                "attributes": {"switch": "off"},
            },
        ]

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
        {"room": "Bedroom 3", "lights_off": ["Bedroom 3 Light"]},
    ]
    assert "Hallway Light" not in answer["message"]
    assert answer["display"]["metrics"][2]["value"] == "2"


def test_webui_displays_ai_provider_badge():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.13-alpha"))

    assert "if(answer.ai_provider)" in page
    assert "Ollama Cloud" not in page or "ai_provider" in page
    assert "mcp-motion-light-state-unavailable" not in page or "routeLabel" in page
