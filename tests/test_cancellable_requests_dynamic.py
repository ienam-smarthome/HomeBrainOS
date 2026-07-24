from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from cancellable_requests import install_cancellable_ask  # noqa: E402


class AskRequest:
    def __init__(self, query: str, session_id: str | None = None) -> None:
        self.query = query
        self.session_id = session_id

    @classmethod
    def model_validate(cls, payload):
        return cls(str(payload.get("query") or ""), payload.get("session_id"))


def test_api_route_uses_handler_installed_after_route_creation():
    api = FastAPI()

    async def old_handler(_request):
        return {"message": "old", "route": "old"}

    application = SimpleNamespace(app=api, ask=old_handler, AskRequest=AskRequest)
    install_cancellable_ask(application)

    async def thermostat_handler(request):
        assert request.query == "What is the thermostat setpoint"
        return {
            "message": "The thermostat heating setpoint is 12°C.",
            "route": "mcp-thermostat-live-state",
        }

    application.ask = thermostat_handler

    with TestClient(api) as client:
        response = client.post(
            "/api/ask",
            json={"query": "What is the thermostat setpoint"},
            headers={"X-HMCP-Client": "thermostat-test"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "message": "The thermostat heating setpoint is 12°C.",
        "route": "mcp-thermostat-live-state",
    }
