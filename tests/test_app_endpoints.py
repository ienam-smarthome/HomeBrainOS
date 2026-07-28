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


def test_root_renders_gemini_webui(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)
    with TestClient(module.app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Gemini model" in response.text
    assert "Ollama model" not in response.text
    assert "fetch('api/status')" in response.text
    assert "fetch('/api/status')" not in response.text
