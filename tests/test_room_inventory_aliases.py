from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module():
    path = Path('hubitat-mcp-ai/rootfs/app/fast_fallback_room_inventory.py')
    spec = importlib.util.spec_from_file_location('room_inventory_test_module', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_room_candidate_extracts_living_room() -> None:
    module = load_module()
    assert module.FastFallbackRouter._room_candidate('Show devices in the living room') == 'living room'


def test_room_keys_ignore_spacing_and_punctuation() -> None:
    module = load_module()
    key = module.FastFallbackRouter._room_key
    assert key('Livingroom') == key('living room') == key('living-room')
    assert key('Bedroom1') == key('bedroom 1') == key('Bedroom-1')
