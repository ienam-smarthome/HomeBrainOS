from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from home_snapshot_truthful import TruthfulHomeSnapshotService  # noqa: E402
from mcp_client import MCPToolResult  # noqa: E402


class FakeMCP:
    async def call_tool(self, name: str, arguments: dict[str, Any]):
        return MCPToolResult(
            name=name,
            arguments=arguments,
            raw={},
            text="",
            data={"safeMode": False, "healthAlerts": {"active": []}},
            is_error=False,
        )


class RecoveringIndex:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    async def enriched_devices(self, *, force: bool = False):
        self.calls.append(force)
        if not force:
            return [
                {"id": "1", "label": "Bedroom 2 Light", "room": "Bedroom 2"},
                {"id": "2", "label": "Bedroom 2 FP1", "room": "Bedroom 2"},
            ]
        return [
            {
                "id": "1",
                "label": "Bedroom 2 Light",
                "room": "Bedroom 2",
                "currentStates": {"switch": "on"},
            },
            {
                "id": "2",
                "label": "Bedroom 2 FP1",
                "room": "Bedroom 2",
                "currentStates": {"motion": "active"},
            },
        ]

    async def diagnostics(self, *, force: bool = False):
        return {
            "selected_count": 2,
            "last_refresh_age_seconds": 0,
            "rooms": ["Bedroom 2"],
            "state_records": 2 if force else 0,
        }

    @staticmethod
    def _groups(item: dict[str, Any]) -> set[str]:
        attrs = item.get("currentStates") or {}
        groups = set()
        if "switch" in attrs:
            groups.add("light")
        if "motion" in attrs:
            groups.add("motion")
        return groups


class EmptyStateIndex(RecoveringIndex):
    async def enriched_devices(self, *, force: bool = False):
        self.calls.append(force)
        return [
            {"id": "1", "label": "Bedroom 2 Light", "room": "Bedroom 2"},
            {"id": "2", "label": "Bedroom 2 FP1", "room": "Bedroom 2"},
        ]

    async def diagnostics(self, *, force: bool = False):
        return {
            "selected_count": 2,
            "last_refresh_age_seconds": 0,
            "rooms": ["Bedroom 2"],
            "state_records": 0,
        }


class FakeOllama:
    model = "qwen3.5:4b"
    num_ctx = 2048

    async def health(self):
        return {"online": True, "models": [self.model]}

    def _resolve_routine_model(self, installed):
        return self.model

    async def _chat(self, **kwargs):
        raise AssertionError("Ollama must not be called in these deterministic tests")


def app() -> SimpleNamespace:
    return SimpleNamespace(mcp=FakeMCP(), ollama=FakeOllama())


def test_snapshot_force_recovers_states_before_reporting_counts():
    index = RecoveringIndex()
    service = TruthfulHomeSnapshotService(app(), index, ai_enabled=False)

    answer = asyncio.run(service.answer("What looks unusual at home right now?"))

    assert index.calls == [False, True]
    assert answer["success"] is True
    assert answer["state_recovery_attempted"] is True
    assert answer["snapshot"]["states_read"] == 2
    assert [metric["value"] for metric in answer["display"]["metrics"]] == [
        "1",
        "1",
        "0",
        "0",
    ]
    assert "Bedroom 2 FP1" in answer["message"]
    assert "Bedroom 2 Light" in answer["message"]
    assert "state scan unavailable" not in answer["display"]["subtitle"]


def test_snapshot_never_turns_missing_states_into_zero_activity():
    index = EmptyStateIndex()
    service = TruthfulHomeSnapshotService(app(), index, ai_enabled=True)

    answer = asyncio.run(service.answer("What looks unusual at home right now?"))

    assert index.calls == [False, True]
    assert answer["success"] is False
    assert answer["route"] == "mcp-snapshot-state-unavailable"
    assert answer["coverage_complete"] is False
    assert answer["snapshot"]["states_read"] == 0
    assert [metric["value"] for metric in answer["display"]["metrics"]] == [
        "—",
        "—",
        "—",
        "—",
    ]
    assert "state scan unavailable" in answer["display"]["subtitle"]
    assert "did not convert missing states into zero motion or zero lights" in answer["display"]["note"]
    assert "I could not verify current motion" in answer["message"]
    assert answer["synthesis_error"] is None
