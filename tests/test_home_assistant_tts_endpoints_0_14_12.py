from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))


def _load_app(monkeypatch, tmp_path):
    options = tmp_path / "options.json"
    options.write_text(
        '{"morning_health_check_enabled": false, "ha_tts_enabled": true}',
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(options))
    monkeypatch.setenv("HEALTH_AUDIT_PATH", str(tmp_path / "health.json"))
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-supervisor-token")
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_native_tts_endpoint_sends_text(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)
    captured = {}

    class TTS:
        def status(self):
            return {"enabled": True, "can_attempt": True}

        async def speak(self, text):
            captured["text"] = text
            return {
                "sent": True,
                "service": "notify.mobile_app_s25_ultra",
                "method": "home-assistant-mobile-app",
            }

        async def stop(self):
            return {
                "sent": True,
                "service": "notify.mobile_app_s25_ultra",
                "method": "home-assistant-mobile-app",
            }

        async def close(self):
            return None

    monkeypatch.setattr(module, "home_assistant_tts", TTS())

    with TestClient(module.app) as client:
        response = client.post("/api/tts", json={"text": "Bedroom 2 Light is on."})

    assert response.status_code == 200
    assert captured["text"] == "Bedroom 2 Light is on."
    assert response.json()["method"] == "home-assistant-mobile-app"


def test_native_tts_configuration_error_is_visible(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)

    class TTS:
        def status(self):
            return {"enabled": True, "can_attempt": True}

        async def speak(self, text):
            raise module.HomeAssistantTTSConfigurationError(
                "Multiple mobile-app notify services were found"
            )

        async def stop(self):
            return {"sent": True}

        async def close(self):
            return None

    monkeypatch.setattr(module, "home_assistant_tts", TTS())

    with TestClient(module.app) as client:
        response = client.post("/api/tts", json={"text": "Hello"})

    assert response.status_code == 409
    assert "Multiple mobile-app notify services" in response.json()["detail"]


def test_status_reports_native_tts_capability(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)

    class TTS:
        def status(self):
            return {
                "enabled": True,
                "token_available": True,
                "notify_service": "notify.mobile_app_s25_ultra",
                "auto_discovery": False,
                "can_attempt": True,
            }

        async def close(self):
            return None

    monkeypatch.setattr(module, "home_assistant_tts", TTS())

    async def fake_health():
        return {"online": True}

    monkeypatch.setattr(module.mcp, "health", fake_health)

    with TestClient(module.app) as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["tts"]["can_attempt"] is True
    assert response.json()["tts"]["notify_service"] == "notify.mobile_app_s25_ultra"


def test_webui_contains_native_tts_fallback(monkeypatch, tmp_path) -> None:
    module = _load_app(monkeypatch, tmp_path)

    with TestClient(module.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "api/tts" in response.text
    assert "api/tts/stop" in response.text
    assert "speakViaHomeAssistant" in response.text
    assert "TTS setup needed" in response.text
    assert "setTimeout(()=>{if(activeSpeech===utterance&&!browserStarted)" in response.text
