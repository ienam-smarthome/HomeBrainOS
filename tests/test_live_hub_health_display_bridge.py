from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from hub_health_display_bridge import (  # noqa: E402
    enhance_hub_health_answer,
    install_hub_health_display_bridge,
)


def _answer(*, available: bool, available_version: str | None = None):
    platform = {"available": available, "currentVersion": "2.5.1.134"}
    if available_version:
        platform["availableVersion"] = available_version
    technical = "Request performance\n{}\n\nMCP response\n" + json.dumps(
        {
            "hub_info": {
                "firmwareVersion": "2.5.1.134",
                "databaseSizeKB": "156",
                "platformUpdate": platform,
            },
            "cpu_probe": {"percent": 43.2},
        }
    )
    return {
        "success": True,
        "route": "mcp-fast",
        "message": "Hub status: Hub C8 Pro.\nPlatform update: Up to date.",
        "technical": technical,
        "display": {
            "kind": "hub-health",
            "title": "Hub C8 Pro",
            "metrics": [
                {"label": "Firmware", "value": "2.5.1.134", "icon": "🧩"},
                {"label": "CPU load", "value": "43.2%", "icon": "🧠"},
            ],
            "items": [],
            "note": "Database: 156 MB",
        },
    }


def _metrics(answer):
    return {item["label"]: item["value"] for item in answer["display"]["metrics"]}


def test_live_bridge_moves_database_note_into_tile_and_marks_current_firmware():
    answer = enhance_hub_health_answer(_answer(available=False))
    metrics = _metrics(answer)
    assert metrics["Installed firmware"] == "2.5.1.134"
    assert metrics["Software update"] == "Up to date"
    assert metrics["Database size"] == "156 MB"
    assert answer["display"]["note"] is None


def test_live_bridge_shows_available_firmware_version():
    answer = enhance_hub_health_answer(
        _answer(available=True, available_version="2.5.1.135")
    )
    assert _metrics(answer)["Software update"] == "Available 2.5.1.135"


def test_installer_wraps_actual_application_ask():
    async def original(_request):
        return _answer(available=False)

    application = SimpleNamespace(ask=original)
    install_hub_health_display_bridge(application)
    answer = asyncio.run(application.ask(SimpleNamespace(query="Check the hub health status")))
    assert _metrics(answer)["Database size"] == "156 MB"
