from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))


def load_app(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_chat_and_ask_use_unified_agent(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)
    calls = []

    async def answer(prompt, history, *, session_id):
        calls.append((prompt, session_id))
        return "Completed."

    monkeypatch.setattr(module.agent, "process_user_request", answer)
    with TestClient(module.app) as client:
        chat = client.post("/api/chat", json={"prompt": "Lights?", "session_id": "mobile"})
        ask = client.post("/api/ask", json={"query": "Lights?", "session_id": "web"})

    assert chat.status_code == 200
    assert chat.json() == {"response": "Completed."}
    assert ask.status_code == 200
    assert ask.json()["route"] == "unified-mcp-agent"
    assert calls == [("Lights?", "mobile"), ("Lights?", "web")]


def test_empty_prompt_is_rejected(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)
    with TestClient(module.app) as client:
        response = client.post("/api/chat", json={"prompt": " "})
    assert response.status_code == 422


def test_root_renders_ollama_dashboard_webui(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)
    with TestClient(module.app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Ollama model" in response.text
    assert "Read answers aloud" in response.text
    assert "Technical details" in response.text
    assert "api/dashboard" in response.text
    assert "hmcp_last_query" in response.text
    assert "query.value=text" in response.text
    assert "document.execCommand('copy')" in response.text
    assert "Copy technical" in response.text
    assert "renderMessage" in response.text
    assert "speechText" in response.text
    assert 'id="micFab"' in response.text
    assert "copy-button" in response.text
    assert "apiPath('api/status')" in response.text
    assert "location.pathname.replace" in response.text
    assert "globalThis.crypto?.randomUUID?.()" in response.text
    assert "Math.random().toString(36)" in response.text
    assert "new AbortController()" in response.text
    assert "activeRequest.abort()" in response.text
    assert "sequence===requestSequence" in response.text
    assert "Ask another question to replace this request." in response.text
    assert "ask.disabled=true" not in response.text
    assert "🔊 Read answer" in response.text
    assert "■ Stop audio" in response.text
    assert "function stopAudio()" in response.text
    assert "function speakAnswer(" in response.text
    assert "function startVoice(){stopAudio()" in response.text
    assert "fetch('/api/status')" not in response.text


def test_dashboard_counts_current_states(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)

    async def devices():
        return [
            {
                "id": "1",
                "capabilities": ["Switch", "Light"],
                "currentStates": [
                    {"name": "switch", "currentValue": "on"},
                    {"name": "battery", "currentValue": 15},
                ],
            },
            {
                "id": "2",
                "capabilities": ["MotionSensor"],
                "currentStates": [{"name": "motion", "currentValue": "active"}],
            },
            {
                "id": "3",
                "capabilities": ["Switch"],
                "currentStates": [{"name": "switch", "currentValue": "on"}],
            },
        ]

    monkeypatch.setattr(module.mcp, "get_cached_devices", devices)
    with TestClient(module.app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "devices": 3,
        "lights_on": 1,
        "motion_active": 1,
        "switches_on": 1,
        "low_batteries": 1,
    }


def test_dashboard_counts_detailed_attributes(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)

    async def devices():
        return [
            {
                "id": "1",
                "capabilities": ["Switch", "Light"],
                "attributes": [
                    {"name": "switch", "value": "on"},
                    {"name": "battery", "value": 12},
                ],
            },
            {
                "id": "2",
                "capabilities": ["MotionSensor"],
                "attributes": [{"name": "motion", "value": "active"}],
            },
        ]

    monkeypatch.setattr(module.mcp, "get_cached_devices", devices)
    with TestClient(module.app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json()["lights_on"] == 1
    assert response.json()["motion_active"] == 1
    assert response.json()["low_batteries"] == 1
