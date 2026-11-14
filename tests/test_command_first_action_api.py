"""Fixture-only API proof: pending action projection and cancellation are not writes."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from tool_registry import ToolEffect


def _app(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_web_app_enables_genuine_queued_routine_approvals(monkeypatch, tmp_path):
    module = _app(monkeypatch, tmp_path)
    assert module.agent.confirmation_policy.requires_confirmation(
        ToolEffect.ROUTINE_WRITE
    )
    assert module.agent.confirmation_policy.requires_confirmation(
        ToolEffect.SENSITIVE_WRITE
    )
    assert not module.agent.confirmation_policy.requires_confirmation(
        ToolEffect.READ
    )


def test_ask_projects_only_pending_structured_action_and_dismisses_safely(
    monkeypatch, tmp_path,
):
    module = _app(monkeypatch, tmp_path)
    session = "fixture-session"
    submitted = []
    def queue():
        module.agent.confirmations.queue(
            session,
            [("hub_manage_devices", {"tool": "hub_call_device_command",
                                     "args": {"deviceId": "DEMO-1", "command": "off",
                                              "apiKey": "SECRET-TEST-TOKEN"}})],
            [{"role": "user", "content": "Fictional command"}],
            {"role": "assistant", "content": ""},
        )
    queue()

    async def fake_answer(request, connection=None):
        submitted.append(request.message)
        return SimpleNamespace(
            message="A fictional native operation is awaiting approval.",
            request_class="write",
            evidence=[],
            choices=[],
            confirmation_required=True,
            confirmation_count=1,
            route="fixture-only",
            metrics={},
        )
    monkeypatch.setattr(module, "_answer_result", fake_answer)
    with TestClient(module.app) as client:
        response = client.post("/api/ask", json={
            "query": "Show the fictional queued action",
            "session_id": session,
        })
        assert response.status_code == 200
        result = response.json()
        assert result["confirmation_required"] is True
        card = result["pending_action_card"]
        assert card["effect_class"] == "routine_write"
        assert card["actions"][0]["command"] == "off"
        assert card["actions"][0]["fields"][0] == {
            "kind": "device", "value": "DEMO-1"
        }
        assert "SECRET-TEST-TOKEN" not in str(card)
        assert submitted == ["Show the fictional queued action"]
        dismissed = client.post("/api/confirmation/dismiss", json={
            "session_id": session,
        })
        assert dismissed.status_code == 200
        assert dismissed.json() == {
            "success": True,
            "cancelled": True,
            "native_write_submitted": False,
        }
        assert session not in module.agent.confirmations.pending
        # Even a stale confirmation_requested flag cannot fabricate an
        # approval action once the authoritative pending session is gone.
        after = client.post("/api/ask", json={
            "query": "Read-only follow-up", "session_id": session,
        })
        assert after.status_code == 200
        assert "pending_action_card" not in after.json()
