from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))


def _load_app(monkeypatch, tmp_path):
    monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "missing-options.json"))
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_dashboard_uses_bulk_context_without_forcing_detailed_manifest(
    monkeypatch, tmp_path
) -> None:
    module = _load_app(monkeypatch, tmp_path)
    calls = {"context": 0, "manifest": 0}

    async def live_context():
        calls["context"] += 1
        return {
            "devices": [
                {
                    "id": "1",
                    "label": "Living Room Motion",
                    "room": "Living Room",
                    "capabilities": ["MotionSensor"],
                    "attributes": {"motion": "active", "battery": "60"},
                },
                {
                    "id": "2",
                    "label": "Kitchen Light",
                    "room": "Kitchen",
                    "capabilities": ["Switch", "Light"],
                    "attributes": {"switch": "on", "battery": "15"},
                },
            ],
            "totalDevices": 2,
            "partial": False,
            "truncated": False,
        }

    async def detailed_manifest(*args, **kwargs):
        calls["manifest"] += 1
        raise AssertionError("dashboard must not force a detailed manifest refresh")

    monkeypatch.setattr(module.mcp, "get_live_context", live_context)
    monkeypatch.setattr(module.mcp, "get_cached_devices", detailed_manifest)

    with TestClient(module.app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "bulk-live-context"
    assert body["devices"] == 2
    assert body["lights_on"] == 1
    assert body["motion_active"] == 1
    assert body["low_batteries"] == 1
    assert body["active_rooms"] == [
        {"name": "Kitchen", "reasons": ["light on"]},
        {"name": "Living Room", "reasons": ["motion"]},
    ]
    assert calls == {"context": 1, "manifest": 0}
