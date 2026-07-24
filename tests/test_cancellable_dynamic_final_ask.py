from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from cancellable_requests import install_cancellable_ask  # noqa: E402


class AskRequest(BaseModel):
    query: str


def test_api_ask_resolves_terminal_handler_at_request_time():
    async def old_handler(_request):
        return {"route": "ollama+mcp", "message": "old handler"}

    application = SimpleNamespace(app=FastAPI(), AskRequest=AskRequest, ask=old_handler)
    install_cancellable_ask(application)

    async def thermostat_handler(request):
        assert request.query == "What is the thermostat setpoint"
        return {
            "success": True,
            "route": "mcp-thermostat-live-state",
            "message": "The thermostat heating setpoint is 12°C.",
            "tools_used": [{"name": "hub_read_devices", "success": True}],
        }

    # This controller is installed after /api/ask. The endpoint must use the current
    # final handler rather than the handler that existed during route installation.
    application.ask = thermostat_handler

    with TestClient(application.app) as client:
        response = client.post(
            "/api/ask",
            json={"query": "What is the thermostat setpoint"},
            headers={"X-HMCP-Client": "thermostat-regression"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "mcp-thermostat-live-state"
    assert payload["tools_used"] == [{"name": "hub_read_devices", "success": True}]
    assert "12°C" in payload["message"]
