from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from answer_guard_registry import AnswerGuardRegistry
from hub_health_display_bridge import hub_health_display_guard


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "hubitat-mcp-ai" / "rootfs" / "app" / "entrypoint.py"


def run(coro):
    return asyncio.run(coro)


def _hub_health_answer() -> dict:
    return {
        "message": "Hub health is available.",
        "display": {
            "kind": "hub-health",
            "metrics": [
                {"label": "Firmware", "value": "unknown"},
                {"label": "Hub update", "value": "unknown"},
            ],
            "note": "Database: 42 MB",
        },
        "technical": json.dumps(
            {
                "hub_info": {
                    "firmwareVersion": "2.4.1.170",
                    "platformUpdate": {
                        "available": False,
                        "currentVersion": "2.4.1.170",
                    },
                }
            }
        ),
    }


def test_hub_health_display_guard_enhances_matching_display():
    answer = run(
        hub_health_display_guard(
            SimpleNamespace(query="hub health"),
            _hub_health_answer(),
        )
    )

    metrics = {item["label"]: item["value"] for item in answer["display"]["metrics"]}
    assert metrics["Installed firmware"] == "2.4.1.170"
    assert metrics["Software update"] == "None reported"
    assert metrics["Database size"] == "42 MB"
    assert answer["display"]["note"] is None


def test_registry_delegates_once_and_leaves_non_hub_display_unchanged():
    calls = []

    async def base(request):
        calls.append(request.query)
        return {"message": "ordinary", "display": {"kind": "summary"}}

    app = SimpleNamespace(ask=base)
    registry = AnswerGuardRegistry(app)
    registry.register_guard("hub-health-display", hub_health_display_guard)
    handler = registry.install()

    answer = run(handler(SimpleNamespace(query="status")))

    assert calls == ["status"]
    assert answer == {"message": "ordinary", "display": {"kind": "summary"}}


def test_public_entrypoint_uses_hub_health_display_registry_at_same_position():
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert "from hub_health_display_bridge import hub_health_display_guard" in source
    assert 'register_guard(\n    "hub-health-display",\n    hub_health_display_guard,' in source
    assert '"hub-health-display-registry",\n    hub_health_guard_registry.install,' in source
    assert "install_hub_health_display_bridge" not in source
    assert source.index("named-app-control") < source.index("hub-health-display-registry")
    assert source.index("hub-health-display-registry") < source.index("semantic-home-summary")
