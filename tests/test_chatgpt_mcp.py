from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))


def load_mcp(monkeypatch, tmp_path):
    options = tmp_path / "options.json"
    options.write_text(
        '{"chatgpt_mcp_enabled":true,"chatgpt_mcp_require_bearer_auth":true,'
        '"chatgpt_mcp_token":"test-secret"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(options))
    sys.modules.pop("chatgpt_mcp", None)
    sys.modules.pop("app", None)
    return importlib.import_module("chatgpt_mcp")


def test_chatgpt_mcp_requires_auth_and_exposes_tools(monkeypatch, tmp_path):
    module = load_mcp(monkeypatch, tmp_path)

    with TestClient(module.core.app) as client:
        unauthorized = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert unauthorized.status_code == 401

        initialized = client.post(
            "/mcp",
            headers={"Authorization": "Bearer test-secret"},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"},
            },
        )
        assert initialized.status_code == 200
        session_id = initialized.headers["mcp-session-id"]
        assert initialized.json()["result"]["serverInfo"]["name"] == "homebrainos"

        tools = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer test-secret",
                "Mcp-Session-Id": session_id,
            },
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
        )

    assert tools.status_code == 200
    definitions = {tool["name"]: tool for tool in tools.json()["result"]["tools"]}
    assert set(definitions) == {
        "homebrain_status",
        "homebrain_dashboard",
        "homebrain_ask",
    }
    assert definitions["homebrain_status"]["annotations"]["readOnlyHint"] is True
    assert definitions["homebrain_ask"]["annotations"]["readOnlyHint"] is False


def test_homebrain_ask_reuses_mcp_session_for_confirmation_scope(monkeypatch, tmp_path):
    module = load_mcp(monkeypatch, tmp_path)
    seen = []

    async def answer_result(request, connection=None):
        seen.append(request.session_id)
        return SimpleNamespace(
            message="Please confirm.",
            request_class="mutation",
            evidence=[],
            confirmation_required=True,
        )

    monkeypatch.setattr(module.core, "_answer_result", answer_result)

    with TestClient(module.core.app) as client:
        initialized = client.post(
            "/mcp",
            headers={"Authorization": "Bearer test-secret"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        session_id = initialized.headers["mcp-session-id"]
        response = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer test-secret",
                "Mcp-Session-Id": session_id,
            },
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "homebrain_ask",
                    "arguments": {"prompt": "Turn off the hallway lights"},
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["content"][0]["text"] == "Please confirm."
    assert seen == [session_id]
