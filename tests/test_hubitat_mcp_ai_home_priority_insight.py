from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from home_priority_insight import (  # noqa: E402
    WholeHomePriorityInsight,
    is_home_priority_query,
    requested_issue_limit,
)


QUERY = "What are the three most important issues at home right now?"


class FakeSnapshotService:
    async def _load_sources(self, *, force: bool, coverage_errors: list[str]):
        return ([{"id": "1"}], {"last_refresh_age_seconds": 0}, {"items": []})

    def _build_snapshot(self, devices, diagnostics, hub_status):
        return {
            "selected_devices": 105,
            "states_read": 105,
            "index_age_seconds": 0,
            "rooms": ["Living Room"],
            "lights_on": [],
            "devices_on": [],
            "background_on": [],
            "motion_active": [],
            "open_contacts": [
                {
                    "icon": "🚪",
                    "title": "Microwave Door",
                    "value": "Open",
                    "subtitle": "Appliances",
                    "priority": 20,
                }
            ],
            "heating": [],
            "attention": [
                {
                    "icon": "📡",
                    "title": "Roborock Q7 Max",
                    "value": "Offline",
                    "subtitle": "Device is not responding",
                    "priority": 2,
                },
                {
                    "icon": "🪫",
                    "title": "Fridge Door",
                    "value": "15%",
                    "subtitle": "Replace soon",
                    "priority": 15,
                },
            ],
        }

    @staticmethod
    def _truthful_subtitle(snapshot, errors, *, states_available):
        return "Updated just now · live Hubitat MCP · 105 selected devices checked"

    @staticmethod
    def _truthful_coverage_note(
        snapshot,
        errors,
        *,
        states_available,
        recovery_attempted,
    ):
        return "Live states were available for 105 of 105 selected devices."


class FakeOllama:
    num_ctx = 2048

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def health(self):
        return {"online": True, "models": ["gemma4:31b-cloud"]}

    @staticmethod
    def _resolve_routine_model(installed):
        return "gemma4:31b-cloud"

    async def _chat(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.fail:
            raise RuntimeError("direct cloud unavailable")
        assert kwargs["tools"] is None
        assert "Current request: " + QUERY in kwargs["messages"][1]["content"]
        return {
            "message": {
                "role": "assistant",
                "content": (
                    "1. Roborock Q7 Max is offline.\n"
                    "2. Fridge Door battery is at 15%.\n"
                    "3. Microwave Door is open."
                ),
            },
            "_homebrain_model_used": "gemma4:31b-cloud",
            "_homebrain_provider": "Ollama Cloud Direct",
        }


class FakeApplication:
    VERSION = "0.6.5"

    def __init__(self, *, fail_ai: bool = False) -> None:
        self.ollama = FakeOllama(fail=fail_ai)
        self.OPTIONS = {
            "home_snapshot_ai_enabled": True,
            "home_snapshot_ai_timeout_seconds": 20,
        }

    @staticmethod
    def option_bool(name: str, default: bool = False) -> bool:
        return default


def test_exact_home_priority_wording_is_not_a_metric_comparison_request():
    assert is_home_priority_query(QUERY)
    assert requested_issue_limit(QUERY) == 3
    assert is_home_priority_query("What looks unusual at home right now?")
    assert not is_home_priority_query("Which device is using the most power?")


def test_home_priority_uses_direct_cloud_after_verified_snapshot():
    application = FakeApplication()
    service = WholeHomePriorityInsight(
        application,
        FakeSnapshotService(),
        ai_enabled=True,
        ai_timeout_seconds=20,
    )

    answer = asyncio.run(service.answer(QUERY))

    assert answer["success"] is True
    assert answer["route"] == "ollama+home-insight"
    assert answer["intent"] == "home-priority-insight"
    assert answer["model"] == "gemma4:31b-cloud"
    assert answer["ai_provider"] == "Ollama Cloud Direct"
    assert answer["requested_issue_count"] == 3
    assert [item["title"] for item in answer["confirmed_issues"]] == [
        "Roborock Q7 Max",
        "Fridge Door",
        "Microwave Door",
    ]
    assert len(application.ollama.calls) == 1
    assert "natural Ollama agent could not complete" not in answer["message"]


def test_home_priority_keeps_deterministic_answer_when_cloud_is_unavailable():
    application = FakeApplication(fail_ai=True)
    service = WholeHomePriorityInsight(
        application,
        FakeSnapshotService(),
        ai_enabled=True,
        ai_timeout_seconds=20,
    )

    answer = asyncio.run(service.answer(QUERY))

    assert answer["route"] == "mcp-home-insight"
    assert "model" not in answer
    assert "Roborock Q7 Max" in answer["message"]
    assert "Fridge Door" in answer["message"]
    assert "Microwave Door" in answer["message"]
    assert answer["synthesis_error"] == "direct cloud unavailable"
    assert "local fallback does not support" not in answer["message"]


def test_late_route_is_installed_after_semantic_pipeline_and_release_is_aligned():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    route_source = (APP_DIR / "device_health_fast_route.py").read_text(encoding="utf-8")
    config = (ROOT / "hubitat-mcp-ai" / "config.yaml").read_text(encoding="utf-8")

    assert entrypoint.index("install_semantic_read_pipeline(") < entrypoint.index(
        "install_device_health_fast_route(application)"
    )
    assert "is_home_priority_query(query)" in route_source
    assert 'RouteDecision(\n                "home-insight"' in route_source
    assert 'version: "0.6.5"' in config
    assert 'RELEASE_VERSION = "0.6.5"' in entrypoint
