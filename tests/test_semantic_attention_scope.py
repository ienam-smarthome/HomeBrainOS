from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = (
    Path(__file__).resolve().parents[1]
    / "hubitat-mcp-ai"
    / "rootfs"
    / "app"
)
sys.path.insert(0, str(APP_DIR))

from semantic_home_query_router import (
    _attention_fallback,
    _filter_attention_scope,
    _requested_attention_scope,
)


FULL_ATTENTION = {
    "low_batteries": {
        "count": 2,
        "items": [
            {"device": "Livingroom TRV", "value": 10},
            {"device": "Fridge Door", "value": 14},
        ],
    },
    "offline": {
        "count": 2,
        "items": [
            {"device": "Roborock Q7 Max", "value": "Offline"},
            {
                "device": "Tuya Remote (bedroom 3)",
                "value": "Offline",
            },
        ],
    },
    "stale": {"count": 1, "items": [{"device": "Old Sensor"}]},
    "warnings": {"count": 0, "items": []},
    "updates": {"count": 0, "items": []},
    "open_contacts": {
        "open_count": 1,
        "open": [{"device": "Front Door"}],
    },
    "lights_on": {
        "on_count": 1,
        "on": [{"title": "Livingroom Light 1"}],
    },
    "issue_count": 5,
}


def test_offline_query_requests_offline_scope():
    assert _requested_attention_scope("offline devices") == "offline"
    assert (
        _requested_attention_scope("Which devices are offline?")
        == "offline"
    )


def test_low_battery_query_requests_battery_scope():
    assert (
        _requested_attention_scope("show low batteries")
        == "low_batteries"
    )


def test_broad_attention_question_keeps_all_categories():
    assert _requested_attention_scope("What needs attention?") is None
    assert _requested_attention_scope("Is anything wrong at home?") is None


def test_offline_scope_removes_unrelated_categories():
    scoped = _filter_attention_scope(
        FULL_ATTENTION,
        "offline",
    )

    assert scoped["offline"]["count"] == 2
    assert scoped["low_batteries"]["count"] == 0
    assert scoped["stale"]["count"] == 0
    assert scoped["open_contacts"]["open_count"] == 0
    assert scoped["lights_on"]["on_count"] == 0
    assert scoped["issue_count"] == 2
    assert scoped["requested_scope"] == "offline"


def test_offline_fallback_mentions_only_offline_devices():
    scoped = _filter_attention_scope(
        FULL_ATTENTION,
        "offline",
    )

    message = _attention_fallback(scoped)

    assert "Roborock Q7 Max" in message
    assert "Tuya Remote (bedroom 3)" in message
    assert "Livingroom TRV" not in message
    assert "Fridge Door" not in message
    assert "Old Sensor" not in message


def test_broad_scope_preserves_original_attention():
    scoped = _filter_attention_scope(
        FULL_ATTENTION,
        None,
    )

    assert scoped is FULL_ATTENTION
    assert scoped["issue_count"] == 5
