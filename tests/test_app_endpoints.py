from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

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

    async def answer_result(prompt, history, *, session_id):
        calls.append((prompt, session_id))
        return SimpleNamespace(
            message="Completed.",
            request_class="live-read",
            evidence=[{"tool": "hub_read_devices", "success": True}],
        )

    monkeypatch.setattr(module.agent, "process_user_request_result", answer_result)
    with TestClient(module.app) as client:
        chat = client.post("/api/chat", json={"prompt": "Lights?", "session_id": "mobile"})
        ask = client.post("/api/ask", json={"query": "Lights?", "session_id": "web"})

    assert chat.status_code == 200
    assert chat.json() == {"response": "Completed."}
    assert ask.status_code == 200
    assert ask.json()["route"] == "unified-mcp-agent"
    assert ask.json()["request_class"] == "live-read"
    assert ask.json()["evidence"][0]["tool"] == "hub_read_devices"
    assert calls == [("Lights?", "mobile"), ("Lights?", "web")]


def test_omitted_session_id_gets_its_own_isolated_key_per_request(monkeypatch, tmp_path):
    """Regression test: session_id used to default to the literal string
    "default" for any caller (e.g. a direct public-API request) that
    omitted it, so two unrelated callers who both omitted session_id
    would share one session key -- one caller's pending confirmation or
    "last device" pronoun context could be read, or even confirmed, by
    the other caller's next request. Each request that omits session_id
    must now get its own random key, never the shared literal "default",
    and never the same key as another omitted-session_id request.
    """

    module = load_app(monkeypatch, tmp_path)
    calls = []

    async def answer_result(prompt, history, *, session_id):
        calls.append(session_id)
        return SimpleNamespace(
            message="Completed.",
            request_class="live-read",
            evidence=[],
        )

    monkeypatch.setattr(module.agent, "process_user_request_result", answer_result)
    with TestClient(module.app) as client:
        first = client.post("/api/chat", json={"prompt": "Lights?"})
        second = client.post("/api/chat", json={"prompt": "Lights?"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 2
    assert "default" not in calls
    assert calls[0] != calls[1]
    assert all(session_id for session_id in calls)


def test_stream_idle_timeout_is_wired_to_agent(monkeypatch, tmp_path):
    options = tmp_path / "options.json"
    options.write_text('{"stream_idle_timeout_seconds": 7}', encoding="utf-8")
    monkeypatch.setenv("CONFIG_PATH", str(options))
    sys.modules.pop("app", None)
    module = importlib.import_module("app")

    assert module.agent.stream_idle_timeout_seconds == 7


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
    assert '<span class="muted">Model</span>' in response.text
    assert "Read answers aloud" in response.text
    assert "Technical details" in response.text
    assert "api/dashboard" in response.text
    assert 'id="dashActiveRooms"' in response.text
    assert "Loading live states…" in response.text
    assert 'id="dashActiveRoomNames"' in response.text
    assert 'id="roomGrid"' not in response.text
    assert 'id="hubInfoGrid"' not in response.text
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
    assert "Update hub firmware" in response.text
    assert "suggestedAction==='firmware-update'" in response.text
    assert "JSON.stringify({query:text,history,session_id:sessionId})" in response.text
    assert "data.confirmation_required===true" in response.text
    assert "/please confirm/i.test(rawMessage)" not in response.text
    assert "hmcp_history_" in response.text
    assert "conversationHistory.slice(-8)" in response.text
    assert "ask.disabled=true" not in response.text
    assert "🔊 Read answer" in response.text
    assert "■ Stop audio" in response.text
    assert "function stopAudio()" in response.text
    assert "function speakAnswer(" in response.text
    assert "function startVoice(){stopAudio()" in response.text
    assert "(?:IDs?|device IDs?)" in response.text
    assert ".replace(/=/g,' ')" in response.text
    assert "'$1 hours'" in response.text
    assert ".replace(/\\n+/g,'. ')" in response.text
    assert "utterance.rate=.95" in response.text
    assert "voice.localService" in response.text
    assert "'response time'" in response.text
    assert "fetch('/api/status')" not in response.text


def test_dashboard_counts_current_states(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)

    async def devices():
        return [
            {
                "id": "1",
                "roomName": "Living Room",
                "capabilities": ["Switch", "Light"],
                "currentStates": [
                    {"name": "switch", "currentValue": "on"},
                    {"name": "battery", "currentValue": 15},
                ],
            },
            {
                "id": "2",
                "room": {"name": "Hallway"},
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
        "rooms": 2,
        "assigned_devices": 2,
        "unassigned_devices": 1,
        "room_counts": [
            {"name": "Hallway", "devices": 1},
            {"name": "Living Room", "devices": 1},
        ],
        "active_rooms": [
            {"name": "Hallway", "reasons": ["motion"]},
            {"name": "Living Room", "reasons": ["light on"]},
        ],
        "hub_info": {},
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


def test_dashboard_reads_hub_info_device(monkeypatch, tmp_path):
    module = load_app(monkeypatch, tmp_path)

    async def devices():
        return [
            {
                "id": "1089",
                "label": "Hub Info (C8 Pro)",
                "currentStates": [
                    {"name": "hubModel", "currentValue": "C-8 Pro"},
                    {"name": "firmwareVersionString", "currentValue": "2.5.1.135"},
                    {"name": "hubUpdateStatus", "currentValue": "Update Available"},
                    {"name": "hubUpdateVersion", "currentValue": "2.5.1.136"},
                    {"name": "cpu5Min", "currentValue": 1.28},
                    {"name": "cpuPct", "currentValue": 32.0},
                    {"name": "freeMemory", "currentValue": 770.3},
                    {"name": "internalTemp", "currentValue": 51.9},
                    {"name": "formattedUptime", "currentValue": "3d:17h:16m:36s"},
                    {"name": "dbSize", "currentValue": 170},
                    {"name": "localIP", "currentValue": "192.168.1.239"},
                    {"name": "matterStatus", "currentValue": "online"},
                ],
            }
        ]

    monkeypatch.setattr(module.mcp, "get_cached_devices", devices)
    with TestClient(module.app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    hub = response.json()["hub_info"]
    assert hub["name"] == "Hub Info (C8 Pro)"
    assert hub["model"] == "C-8 Pro"
    assert hub["firmware_version"] == "2.5.1.135"
    assert hub["update_status"] == "Update Available"
    assert hub["update_version"] == "2.5.1.136"
    assert hub["cpu_load"] == 1.28
    assert hub["cpu_percent"] == 32.0
    assert hub["free_memory"] == 770.3


def test_new_automation_idea_request_is_routed_to_the_model_and_falls_back_gracefully(
    monkeypatch, tmp_path
):
    """"Recommend useful automations for my home" must route to the
    creative-suggestion path (model call grounded in real device data),
    not the plain audit/status dump -- and if the model call fails, the
    deterministic gap-analysis message must still come through unchanged
    rather than erroring out.
    """

    module = load_app(monkeypatch, tmp_path)

    from automation_status_service import AutomationStatusOutcome

    async def fake_snapshot(*, advisory):
        assert advisory is True
        return AutomationStatusOutcome(
            message="Fallback deterministic message.",
            automation_items=[{"name": "Unrelated Rule", "display_name": "Unrelated Rule"}],
            devices=[{"id": "1", "label": "Hallway Motion", "capabilities": ["MotionSensor"]}],
        )

    monkeypatch.setattr(module.automation_status, "snapshot", fake_snapshot)

    async def fake_chat(messages, tools):
        assert tools == []
        return {"role": "assistant", "content": "Idea: motion-activated hallway light."}

    monkeypatch.setattr(module.agent.transport, "chat", fake_chat)

    with TestClient(module.app) as client:
        response = client.post(
            "/api/ask",
            json={"query": "Recommend useful automations for my home", "session_id": "web"},
        )

    body = response.json()
    assert body["route"] == "automation-status"
    assert "Idea: motion-activated hallway light." in body["message"]
    assert "Fallback deterministic message." in body["message"]

    # Now simulate the model call failing entirely -- the deterministic
    # message must still be returned, unchanged, with no error surfaced.
    async def failing_chat(messages, tools):
        raise RuntimeError("network down")

    monkeypatch.setattr(module.agent.transport, "chat", failing_chat)

    with TestClient(module.app) as client:
        response = client.post(
            "/api/ask",
            json={"query": "Recommend useful automations for my home", "session_id": "web"},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["message"] == "Fallback deterministic message."


def test_review_existing_automations_request_still_uses_plain_status_route(
    monkeypatch, tmp_path
):
    """A request to review EXISTING automations (not brainstorm new ones)
    must still go through the plain deterministic snapshot -- the new
    creative-suggestion path must not be called for this phrasing.
    """

    module = load_app(monkeypatch, tmp_path)

    calls = {"snapshot_advisory": None, "chat_called": False}

    from automation_status_service import AutomationStatusOutcome

    async def fake_snapshot(*, advisory):
        calls["snapshot_advisory"] = advisory
        return AutomationStatusOutcome(message="Review message.")

    async def fake_chat(messages, tools):
        calls["chat_called"] = True
        return {"role": "assistant", "content": "should not be called"}

    monkeypatch.setattr(module.automation_status, "snapshot", fake_snapshot)
    monkeypatch.setattr(module.agent.transport, "chat", fake_chat)

    with TestClient(module.app) as client:
        response = client.post(
            "/api/ask",
            json={"query": "recommend which of my automations need fixing", "session_id": "web"},
        )

    body = response.json()
    assert body["message"] == "Review message."
    assert calls["snapshot_advisory"] is True
    assert calls["chat_called"] is False
