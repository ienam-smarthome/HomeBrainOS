from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

from semantic_home_query_router import (
    _attention_evidence,
    _authoritative_health_attention,
    _health_attention_items,
)


def test_health_display_items_are_projected_as_offline():
    answer = {
        "display": {
            "items": [
                {
                    "title": "Tuya Remote (bedroom 3)",
                    "value": "Offline",
                    "subtitle": "Live Hubitat healthStatus: offline; rtt timeout",
                    "tone": "danger",
                },
                {
                    "title": "Roborock Q7 Max",
                    "value": "Offline",
                    "subtitle": "Live Hubitat healthStatus: offline",
                    "tone": "danger",
                },
            ]
        }
    }

    items = _health_attention_items(answer)

    assert [item["title"] for item in items] == [
        "Tuya Remote (bedroom 3)",
        "Roborock Q7 Max",
    ]
    assert all(item["value"] == "Offline" for item in items)


def test_health_items_merge_into_attention_classification():
    evidence = {
        "data": {
            "low_batteries": {
                "items": [
                    {
                        "device": "Livingroom TRV",
                        "room": "Thermostat & TRV's",
                        "value": 10.0,
                        "unit": "%",
                    }
                ]
            },
            "attention": [
                {
                    "title": "Roborock Q7 Max",
                    "value": "Offline",
                    "subtitle": "Live Hubitat healthStatus: offline",
                    "tone": "danger",
                },
                {
                    "title": "Tuya Remote (bedroom 3)",
                    "value": "Offline",
                    "subtitle": "rtt timeout",
                    "tone": "danger",
                },
            ],
        }
    }

    attention = _attention_evidence(evidence)

    assert attention["low_batteries"]["count"] == 1
    assert attention["offline"]["count"] == 2
    assert {
        item["device"]
        for item in attention["offline"]["items"]
    } == {
        "Roborock Q7 Max",
        "Tuya Remote (bedroom 3)",
    }
    assert attention["issue_count"] == 3


def test_authoritative_health_reader_uses_existing_fallback():
    class Fallback:
        async def _device_health(self):
            return {
                "success": True,
                "display": {
                    "items": [
                        {
                            "title": "Roborock Q7 Max",
                            "value": "Offline",
                            "subtitle": "wifi offline",
                        }
                    ]
                },
            }

    application = SimpleNamespace(fallback=Fallback())

    items, answer, error = asyncio.run(
        _authoritative_health_attention(application)
    )

    assert error is None
    assert answer["success"] is True
    assert items[0]["title"] == "Roborock Q7 Max"
    assert items[0]["value"] == "Offline"
