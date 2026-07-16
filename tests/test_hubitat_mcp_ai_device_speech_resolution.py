from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from fast_fallback_speech import FastFallbackRouter, normalise_spoken_device_name  # noqa: E402
from fastpath_ai_handoff import install_fastpath_ai_handoff  # noqa: E402
from ollama_agent_device_resolution import DeviceResolutionNaturalAgent  # noqa: E402


def test_spoken_numbers_match_numeric_device_labels():
    candidates = [
        {"id": "1", "label": "Dehumidifier 1"},
        {"id": "2", "label": "Dehumidifier 2"},
    ]
    match, alternatives = FastFallbackRouter._match_device(
        "dehumidifier one",
        candidates,
    )
    assert match == candidates[0]
    assert alternatives == []
    assert normalise_spoken_device_name("Dehumidifier number one") == "dehumidifier 1"


def test_humidifier_does_not_silently_equal_dehumidifier():
    candidates = [
        {"id": "1", "label": "Dehumidifier 1"},
        {"id": "2", "label": "Dehumidifier 2"},
    ]
    match, alternatives = FastFallbackRouter._match_device(
        "humidifier one",
        candidates,
    )
    assert match is None
    assert alternatives[0] == "Dehumidifier 1"


def test_humidity_name_conflict_returns_short_confirmation_without_control():
    async def original_ask(_request):
        return {
            "success": False,
            "intent": "fallback-ambiguous-device",
            "message": "Closest matches: Dehumidifier 1, Dehumidifier 2.",
            "requested_name": "humidifier one",
            "requested_action": "on",
            "alternatives": ["Dehumidifier 1", "Dehumidifier 2"],
        }

    class OllamaMustNotRun:
        async def answer_with_planner(self, query, history):
            raise AssertionError("opposite appliance meanings require confirmation first")

    application = SimpleNamespace(
        ask=original_ask,
        ollama=OllamaMustNotRun(),
        OPTIONS={"ollama_agent_timeout_seconds": 60},
        VERSION="0.2.5-alpha",
    )
    wrapped = install_fastpath_ai_handoff(application)
    request = SimpleNamespace(query="turn on the humidifier one", history=[])
    answer = asyncio.run(wrapped(request))

    assert answer["success"] is False
    assert answer["confirmation_required"] is True
    assert answer["message"] == (
        "Did you mean Dehumidifier 1? Say “turn on Dehumidifier 1” to confirm."
    )
    assert "Air Purifier" not in answer["message"]


def test_automatic_helper_does_not_downgrade_qwen3_to_qwen2():
    agent = DeviceResolutionNaturalAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
    )
    installed = ["qwen2.5:3b", "llama3.2:3b", "qwen3.5:9b"]
    assert agent._resolve_planner_model(installed) == "qwen3.5:9b"
    assert agent._resolve_routine_model(installed) == "qwen3.5:9b"


def test_qwen3_helper_is_used_when_available():
    agent = DeviceResolutionNaturalAgent(
        client=object(),
        base_url="http://ollama:11434",
        model="qwen3.5:9b",
    )
    installed = ["qwen2.5:3b", "qwen3:4b", "qwen3.5:9b"]
    assert agent._resolve_planner_model(installed) == "qwen3:4b"
