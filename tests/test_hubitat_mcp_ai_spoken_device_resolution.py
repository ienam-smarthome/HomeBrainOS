from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_confirmation import install_control_confirmation  # noqa: E402
from device_intelligence_duplicate_safe import (  # noqa: E402
    DuplicateAwareCapabilityCatalogueDeviceIndex,
)
from fast_fallback_speech import FastFallbackRouter  # noqa: E402
from spoken_device_name import spoken_name_key, unique_spoken_match  # noqa: E402


def selected_devices() -> list[dict[str, Any]]:
    return [
        {"id": "1", "label": "Livingroom Light 1", "name": "Livingroom Light 1"},
        {"id": "2", "label": "Livingroom Light 2", "name": "Livingroom Light 2"},
        {"id": "3", "label": "Livingroom TRV", "name": "Livingroom TRV"},
        {"id": "4", "label": "Bathroom Light 2", "name": "Bathroom Light 2"},
    ]


def test_spoken_key_handles_duplicate_letters_spacing_and_number_words():
    assert spoken_name_key("liiving room light two") == spoken_name_key(
        "Livingroom Light 2"
    )
    assert spoken_name_key("hall way light one") == spoken_name_key(
        "Hallway Light 1"
    )


def test_unique_spoken_match_selects_only_the_numbered_full_label():
    labels = [item["label"] for item in selected_devices()]

    assert unique_spoken_match("liiving room light two", labels) == "Livingroom Light 2"
    assert unique_spoken_match("living room light", labels) is None


def test_duplicate_spoken_keys_remain_ambiguous():
    labels = ["Livingroom Light 2", "Living Room Light Two"]

    assert unique_spoken_match("liiving room light two", labels) is None


def test_shared_device_index_resolves_unique_spoken_alias_before_fuzzy_list():
    index = object.__new__(DuplicateAwareCapabilityCatalogueDeviceIndex)

    async def summary_devices(self):
        return selected_devices()

    index.summary_devices = MethodType(summary_devices, index)

    match, alternatives = asyncio.run(
        index.exact_device("liiving room light two")
    )

    assert match is not None
    assert match["id"] == "2"
    assert match["label"] == "Livingroom Light 2"
    assert alternatives == []


def test_fast_control_matcher_uses_same_unique_spoken_key():
    match, alternatives = FastFallbackRouter._match_device(
        "liiving room light two",
        selected_devices(),
    )

    assert match is not None
    assert match["id"] == "2"
    assert alternatives == []


def test_confirmation_layer_reissues_exact_verified_control_without_menu():
    calls: list[str] = []

    async def original_ask(request: Any) -> dict[str, Any]:
        calls.append(str(request.query))
        if str(request.query) == "turn off Livingroom Light 2":
            return {
                "success": True,
                "route": "mcp-fast",
                "intent": "fallback-device-control-confirmed",
                "message": "Livingroom Light 2 confirmed off.",
                "display": {"title": "Device control", "note": "Final state verified."},
            }
        return {
            "success": False,
            "route": "ollama+mcp",
            "intent": "ollama-device-clarification",
            "confirmation_required": True,
            "confirmation": {
                "action": "off",
                "requested_name": "liiving room light two",
                "candidates": [
                    "Livingroom Light 2",
                    "Livingroom Light 1",
                    "Livingroom TRV",
                    "Bathroom Light 2",
                    "Bathroom Light 1",
                ],
            },
        }

    application = SimpleNamespace(ask=original_ask)
    install_control_confirmation(application)
    request = SimpleNamespace(
        query="turn off liiving room light two",
        session_id="speech-test",
        history=[],
    )

    answer = asyncio.run(application.ask(request))

    assert calls == [
        "turn off liiving room light two",
        "turn off Livingroom Light 2",
    ]
    assert answer["success"] is True
    assert answer.get("confirmation_required") is not True
    assert answer["auto_resolved_confirmation"] is True
    assert answer["resolved_device_name"] == "Livingroom Light 2"
    assert answer["spoken_name_resolution"]["method"] == "unique-spoken-key"
    assert "Speech name resolved uniquely" in answer["display"]["note"]


def test_confirmation_remains_required_when_number_is_missing():
    calls: list[str] = []

    async def original_ask(request: Any) -> dict[str, Any]:
        calls.append(str(request.query))
        return {
            "success": False,
            "intent": "ollama-device-clarification",
            "confirmation_required": True,
            "confirmation": {
                "action": "off",
                "requested_name": "living room light",
                "candidates": ["Livingroom Light 1", "Livingroom Light 2"],
            },
        }

    application = SimpleNamespace(ask=original_ask)
    install_control_confirmation(application)
    request = SimpleNamespace(
        query="turn off living room light",
        session_id="ambiguous-test",
        history=[],
    )

    answer = asyncio.run(application.ask(request))

    assert calls == ["turn off living room light"]
    assert answer["success"] is False
    assert answer["confirmation_required"] is True
    assert "1. Livingroom Light 1" in answer["message"]
    assert "2. Livingroom Light 2" in answer["message"]
