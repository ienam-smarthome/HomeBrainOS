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
        assert request.query == "What is thermostat setpoint"
        return {
            "message": "The thermostat heating setpoint is 12°C.",
            "route": "mcp-thermostat-live-state",
            "tools_used": [{"name": "hub_read_devices", "success": True}],
        }

    application.ask = thermostat_handler

    with TestClient(api) as client:
        response = client.post(
            "/api/ask",
            json={"query": "What is thermostat setpoint"},
            headers={"X-HMCP-Client": "thermostat-test"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "mcp-thermostat-live-state"
    assert payload["message"] == "The thermostat heating setpoint is 12°C."
    assert payload["tools_used"] == [{"name": "hub_read_devices", "success": True}]


def test_http_boundary_reads_exact_thermostat_detail_before_ai():
    api = FastAPI()

    class Result:
        def __init__(self, data):
            self.data = data
            self.is_error = False

    class MCP:
        def __init__(self):
            self.calls = []

        async def call_tool(self, name, arguments):
            self.calls.append((name, arguments))
            if name == "hub_list_devices":
                return Result(
                    {
                        "devices": [
                            {
                                "id": "trv-1",
                                "label": "Bedroom 1 TRV",
                                "currentStates": {"temperature": 21},
                            },
                            {
                                "id": "4382",
                                "label": "Thermostat",
                                "currentStates": {"temperature": 25},
                            },
                        ]
                    }
                )
            assert name == "hub_get_device"
            assert arguments == {"deviceId": "4382"}
            return Result(
                {
                    "device": {
                        "id": "4382",
                        "label": "Thermostat",
                        "currentStates": [
                            {"name": "temperature", "currentValue": "25.0"},
                            {"name": "heatingSetpoint", "currentValue": "12.0"},
                            {"name": "coolingSetpoint", "currentValue": "35.0"},
                        ],
                    }
                }
            )

    async def ai_handler(_request):
        raise AssertionError("AI must not run for the exact thermostat setpoint query")

    mcp = MCP()
    application = SimpleNamespace(
        app=api,
        ask=ai_handler,
        AskRequest=AskRequest,
        mcp=mcp,
        device_index=None,
    )
    install_cancellable_ask(application)

    with TestClient(api) as client:
        response = client.post(
            "/api/ask",
            json={"query": "What is thermostat setpoint"},
            headers={"X-HMCP-Client": "thermostat-detail-test"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "mcp-thermostat-live-state"
    assert payload["http_boundary_guard"] is True
    assert "room temperature is 25°C" in payload["message"]
    assert "heating setpoint is 12°C" in payload["message"]
    assert mcp.calls == [
        ("hub_list_devices", {}),
        ("hub_get_device", {"deviceId": "4382"}),
    ]
