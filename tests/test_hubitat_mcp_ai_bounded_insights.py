from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from device_intelligence_webui import patch_page  # noqa: E402
from ollama_engagement import _decorate_snapshot_ai  # noqa: E402
from temperature_insight import TemperatureInsightService  # noqa: E402
from webui import render_page  # noqa: E402


class FakeIndex:
    async def enriched_devices(self):
        return [
            {
                "id": "1",
                "label": "Bedroom 1 Meter",
                "room": "Bedroom 1",
                "currentStates": {"temperature": 22.5},
            },
            {
                "id": "2",
                "label": "Livingroom TRV",
                "room": "Living Room",
                "currentStates": {"temperature": 25.0},
            },
            {
                "id": "3",
                "label": "Bedroom 1 TRV",
                "room": "Bedroom 1",
                "currentStates": {"temperature": 24.0},
            },
            {
                "id": "4",
                "label": "Bedroom 2 Temperature Sensor",
                "room": "Bedroom 2",
                "currentStates": {"temperature": 21.0},
            },
            {
                "id": "5",
                "label": "Bedroom 3 FP300",
                "room": "Bedroom 3",
                "currentStates": {"temperature": 20.5},
            },
        ]


class CategorisedTrvIndex:
    async def enriched_devices(self):
        return [
            {
                "id": "1",
                "label": "Bedroom 1 Meter",
                "room": "Bedroom 1",
                "currentStates": {"temperature": 22.3},
            },
            {
                "id": "2",
                "label": "Bedroom 1 TRV",
                "room": "Thermostat & TRV's",
                "currentStates": {"temperature": 24.6},
            },
            {
                "id": "3",
                "label": "Bedroom 2 TRV",
                "room": "Thermostat & TRV's",
                "currentStates": {"temperature": 24.9},
            },
            {
                "id": "4",
                "label": "Bedroom Three TRV",
                "room": "Thermostat & TRV's",
                "currentStates": {"temperature": 24.0},
            },
        ]


class FakeOllama:
    model = "qwen3.5:4b"
    num_ctx = 2048

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def health(self):
        return {"online": True, "models": ["qwen3.5:4b"]}

    def _resolve_routine_model(self, installed: list[str]) -> str:
        return "qwen3.5:4b"

    async def _chat(self, **kwargs: Any):
        self.calls.append(kwargs)
        if self.fail:
            raise TimeoutError("quick insight timed out")
        return {
            "message": {
                "content": (
                    "Bedroom 3 is coolest at 20.5°C and Bedroom 1 is warmest "
                    "at 22.5°C, a 2°C difference. Different heating demand, "
                    "airflow or sensor position could explain the spread."
                )
            }
        }


def application(ollama: FakeOllama) -> SimpleNamespace:
    return SimpleNamespace(
        ollama=ollama,
        OPTIONS={"ollama_model": "qwen3.5:4b"},
    )


def test_temperature_comparison_skips_planner_and_uses_bounded_evidence():
    ollama = FakeOllama()
    service = TemperatureInsightService(
        application(ollama),
        FakeIndex(),
        timeout_seconds=15,
    )

    answer = asyncio.run(
        service.answer("Compare the bedroom temperatures and explain the difference")
    )

    assert answer["route"] == "ollama+temperature-insight"
    assert answer["ai_used"] is True
    assert answer["answered_by"] == "Ollama"
    assert answer["evidence_source"] == "Hubitat MCP"
    assert [item["room"] for item in answer["readings"]] == [
        "Bedroom 1",
        "Bedroom 2",
        "Bedroom 3",
    ]
    assert answer["readings"][0]["device"] == "Bedroom 1 Meter"
    assert answer["readings"][0]["alternate_sources"] == [
        {"device": "Bedroom 1 TRV", "temperature": 24.0}
    ]
    assert answer["display"]["metrics"][3]["value"] == "2°C"
    assert len(ollama.calls) == 1
    assert ollama.calls[0]["tools"] is None
    prompt = ollama.calls[0]["messages"][1]["content"]
    assert "Verified readings" in prompt
    assert "alternate_sensors" in prompt


def test_temperature_comparison_uses_label_bedroom_over_trv_category_room():
    ollama = FakeOllama()
    service = TemperatureInsightService(
        application(ollama),
        CategorisedTrvIndex(),
        timeout_seconds=15,
    )

    answer = asyncio.run(
        service.answer("Compare the bedroom temperatures and explain the difference")
    )

    assert [item["room"] for item in answer["readings"]] == [
        "Bedroom 1",
        "Bedroom 2",
        "Bedroom 3",
    ]
    assert "Thermostat & TRV's" not in {
        item["room"] for item in answer["readings"]
    }
    assert answer["readings"][0]["device"] == "Bedroom 1 Meter"
    assert answer["readings"][0]["alternate_sources"] == [
        {"device": "Bedroom 1 TRV", "temperature": 24.6}
    ]
    assert answer["readings"][1]["device"] == "Bedroom 2 TRV"
    assert answer["readings"][2]["device"] == "Bedroom Three TRV"
    assert answer["display"]["metrics"][0]["value"] == "3"
    assert any(
        item["title"] == "Bedroom 1 TRV" and item["value"] == "24.6°C"
        for item in answer["display"]["items"]
    )


def test_temperature_comparison_remains_complete_when_ollama_times_out():
    service = TemperatureInsightService(
        application(FakeOllama(fail=True)),
        FakeIndex(),
        timeout_seconds=15,
    )

    answer = asyncio.run(
        service.answer("Compare the bedroom temperatures and explain the difference")
    )

    assert answer["success"] is True
    assert answer["route"] == "mcp-temperature-insight-ai-fallback"
    assert answer["ai_attempted"] is True
    assert answer["ai_used"] is False
    assert answer["answered_by"] == "HomeBrain comparison"
    assert answer["evidence_source"] == "Hubitat MCP"
    assert "Bedroom 1 is 2°C warmer than Bedroom 3" in answer["message"]
    assert "Bedroom 1 also has Bedroom 1 TRV at 24°C" in answer["message"]
    assert "Ollama was attempted but did not finish" in answer["display"]["note"]


def test_snapshot_fallback_explicitly_identifies_who_answered():
    app = SimpleNamespace(OPTIONS={"ollama_model": "qwen3.5:4b"})
    snapshot = SimpleNamespace(ai_enabled=True)

    answer = _decorate_snapshot_ai(
        app,
        snapshot,
        {
            "success": True,
            "route": "mcp-snapshot",
            "message": "Deterministic snapshot",
            "synthesis_error": "timed out",
            "display": {"note": "Live Hubitat data."},
        },
    )

    assert answer["route"] == "mcp-snapshot-ai-fallback"
    assert answer["ai_attempted"] is True
    assert answer["ai_used"] is False
    assert answer["ai_status"] == "fallback"
    assert answer["answered_by"] == "Home Snapshot"
    assert answer["evidence_source"] == "Hubitat MCP"
    assert answer["model"] == "qwen3.5:4b"
    assert "deterministic Home Snapshot" in answer["display"]["note"]


def test_webui_labels_ai_used_and_ai_fallback_routes():
    page = patch_page(render_page("Hubitat MCP AI", "0.4.11-alpha"))

    assert "Ollama comparison" in page
    assert "Hubitat comparison (AI fallback)" in page
    assert "Hubitat snapshot (AI fallback)" in page
    assert "AI attempted → fallback" in page
    assert "answer.ai_used?'AI used'" in page
    assert "'Answered by '+String(answer.answered_by)" in page
