from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from semantic_home_query_router import (  # noqa: E402
    _attention_complete,
    _attention_evidence,
    _attention_fallback,
    _json_object,
)


def sample_evidence():
    return {
        "data": {
            "contacts": {"open_count": 0, "open": []},
            "lights": {"on_count": 0, "on": []},
            "low_batteries": {
                "count": 2,
                "items": [
                    {"device": "Livingroom TRV", "room": "Thermostat", "value": 10.0},
                    {"device": "Fridge Door", "room": "Appliances", "value": 14.0},
                ],
            },
            "attention": [
                {"title": "Tahmid Khan", "value": "6%", "subtitle": "Replace soon", "room": "Life360"},
                {"title": "Livingroom TRV", "value": "10%", "subtitle": "Replace soon", "room": "Thermostat"},
                {"title": "Fridge Door", "value": "14%", "subtitle": "Replace soon", "room": "Appliances"},
                {"title": "Aqara Mini Switch", "value": "Stale 48h+", "subtitle": "Last activity yesterday", "room": "Kitchen"},
                {"title": "Garage Sensor", "value": "Offline", "subtitle": "No response", "room": "Garage"},
            ],
        }
    }


def test_json_classifier_payload_is_parsed_from_fenced_text():
    assert _json_object('```json\n{"intent":"home_attention"}\n```') == {"intent": "home_attention"}
    assert _json_object("not json") is None


def test_attention_evidence_filters_life360_and_deduplicates_low_batteries():
    result = _attention_evidence(sample_evidence())
    assert [item["device"] for item in result["low_batteries"]["items"]] == ["Livingroom TRV", "Fridge Door"]
    assert [item["device"] for item in result["stale"]["items"]] == ["Aqara Mini Switch"]
    assert [item["device"] for item in result["offline"]["items"]] == ["Garage Sensor"]
    assert "Tahmid Khan" not in str(result)
    assert result["issue_count"] == 4


def test_attention_fallback_is_complete_and_natural():
    result = _attention_evidence(sample_evidence())
    message = _attention_fallback(result)
    assert "Livingroom TRV at 10%" in message
    assert "Fridge Door at 14%" in message
    assert "Aqara Mini Switch" in message
    assert "Garage Sensor" in message
    assert "states read" not in message.lower()


def test_attention_validation_requires_every_named_issue():
    result = _attention_evidence(sample_evidence())
    complete = (
        "Garage Sensor is offline. Aqara Mini Switch is stale. "
        "Livingroom TRV and Fridge Door have low batteries."
    )
    assert _attention_complete(complete, result) is True
    assert _attention_complete(complete.replace("Garage Sensor", ""), result) is False
    assert _attention_complete(complete.replace("Fridge Door", ""), result) is False


def test_entrypoint_wires_semantic_router_before_legacy_guard():
    source = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")
    router = source.index("install_semantic_home_query_router(_core.application)")
    guard = source.index("install_home_summary_consistency_guard(_core.application)")
    assert router < guard
    assert 'RELEASE_VERSION = "0.10.85"' in source
