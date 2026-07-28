from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from structured_health_contract import (
    apply_structured_health_contract,
    install_structured_health_contract,
    project_health_attention_items,
)


def _raw_health_answer():
    technical = {
        "offline_devices": [
            {"id": "1", "title": "Iron", "value": "Offline", "reason": "Live healthStatus is offline."},
        ],
        "stale_telemetry": [
            {"id": "2", "title": "Periodic Sensor", "value": "Telemetry stale 48h+", "reason": "Periodic telemetry stopped."},
        ],
        "quiet_timestamp_devices": [
            {"id": "3", "title": "Quiet Helper", "value": "Quiet, not offline", "reason": "Event age only."},
        ],
    }
    return {
        "route": "mcp-fast",
        "display": {
            "items": [
                {"title": "Iron", "value": "Offline", "tone": "danger"},
                {"title": "Periodic Sensor", "value": "Telemetry stale 48h+", "tone": "warning"},
                {"title": "Quiet Helper", "value": "Quiet, not offline", "tone": None},
            ]
        },
        "technical": json.dumps(technical),
    }


def test_contract_preserves_kind_on_display_and_structured_lists():
    result = apply_structured_health_contract(_raw_health_answer())

    assert [item["kind"] for item in result["display"]["items"]] == [
        "offline",
        "stale",
        "quiet",
    ]
    assert [item["id"] for item in result["health_items"]] == ["1", "2", "3"]
    assert result["quiet_devices"][0]["tone"] is None


def test_semantic_projection_drops_quiet_and_uses_explicit_tones():
    projected = project_health_attention_items(_raw_health_answer())

    assert [(item["id"], item["kind"], item["tone"]) for item in projected] == [
        ("1", "offline", "danger"),
        ("2", "stale", "warning"),
    ]
    assert "Quiet Helper" not in str(projected)


def test_installer_wraps_live_reader_and_replaces_legacy_projector(monkeypatch):
    async def reader():
        return _raw_health_answer()

    fallback = SimpleNamespace(_device_health=reader)
    application = SimpleNamespace(fallback=fallback)

    import semantic_home_query_router as semantic_router

    original_projector = semantic_router._health_attention_items
    try:
        installed = install_structured_health_contract(application)
        assert installed is not None
        answer = asyncio.run(application.fallback._device_health())
        assert answer["health_items"][2]["kind"] == "quiet"
        assert semantic_router._health_attention_items is project_health_attention_items
    finally:
        semantic_router._health_attention_items = original_projector
