from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


APP = Path("hubitat-mcp-ai/rootfs/app").resolve()
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def load_module() -> ModuleType:
    path = APP / "fast_fallback_room_inventory.py"
    spec = importlib.util.spec_from_file_location("room_inventory_parser_test_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_show_devices_preserves_room_suffix_as_part_of_name() -> None:
    router = load_module().FastFallbackRouter
    assert router._room_candidate("Show devices in the living room") == "living room"
    assert router._room_key("living room") == router._room_key("Livingroom")


def test_which_devices_preserves_room_suffix_as_part_of_name() -> None:
    router = load_module().FastFallbackRouter
    assert router._room_candidate("Which devices are in the living room?") == "living room"


def test_explicit_room_suffix_form_still_extracts_room_name() -> None:
    router = load_module().FastFallbackRouter
    assert router._room_candidate("Show the Livingroom room devices") == "Livingroom"


def test_room_first_device_inventory_extracts_room_name() -> None:
    router = load_module().FastFallbackRouter
    assert router._room_candidate("Find hallway devices") == "hallway"
    assert router._room_candidate("Show hallway devices") == "hallway"
