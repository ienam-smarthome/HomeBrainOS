from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from location_privacy import REDACTED_PLACEHOLDER, redact_precise_location  # noqa: E402


def _life360_device() -> dict:
    return {
        "devices": [
            {
                "id": "7168",
                "label": "Household Member",
                "room": "Life360",
                "attributes": [
                    {"name": "latitude", "value": "51.4670704"},
                    {"name": "longitude", "value": "-0.0179751"},
                    {"name": "locationUrl", "value": "https://maps.example/?q=51.46,-0.01"},
                    {"name": "presence", "value": "present"},
                    {"name": "battery", "value": 37},
                    {"name": "wifi", "value": "true"},
                    {"name": "tile", "value": "<div>map html with embedded coordinates</div>"},
                    {"name": "address1", "value": "Home"},
                    {"name": "journeysYesterday", "value": "5:12 PM - 5:17 PM | Home -> Elswick Road"},
                    {"name": "resolvedPlace", "value": "Home"},
                    {"name": "lastUpdated", "value": "2026-08-06 17:17:44"},
                ],
            }
        ]
    }


def test_redacts_precise_location_attributes_from_nested_device_result() -> None:
    out = redact_precise_location(_life360_device())
    attrs = {a["name"]: a["value"] for a in out["devices"][0]["attributes"]}

    for sensitive_key in ("latitude", "longitude", "locationUrl", "tile", "address1", "journeysYesterday"):
        assert attrs[sensitive_key] == REDACTED_PLACEHOLDER


def test_preserves_non_location_state_used_by_presence_queries() -> None:
    out = redact_precise_location(_life360_device())
    attrs = {a["name"]: a["value"] for a in out["devices"][0]["attributes"]}

    assert attrs["presence"] == "present"
    assert attrs["battery"] == 37
    assert attrs["wifi"] == "true"
    assert attrs["resolvedPlace"] == "Home"
    assert attrs["lastUpdated"] == "2026-08-06 17:17:44"


def test_leaves_devices_without_location_attributes_untouched() -> None:
    light = {"devices": [{"id": "1", "label": "Kitchen Light", "attributes": [{"name": "switch", "value": "on"}]}]}
    assert redact_precise_location(light) == light


def test_handles_scalars_and_lists_without_error() -> None:
    assert redact_precise_location("plain text") == "plain text"
    assert redact_precise_location(None) is None
    assert redact_precise_location([1, 2, {"latitude": "1.0"}]) == [1, 2, {"latitude": REDACTED_PLACEHOLDER}]