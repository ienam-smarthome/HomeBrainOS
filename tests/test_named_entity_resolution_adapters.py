from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from named_entity_resolution_adapters import install_named_entity_resolution_adapters


class FakeController:
    @staticmethod
    def _requested_id(intent):
        return intent.requested_id


def test_rule_adapter_uses_existing_requested_id_contract():
    app_controller = FakeController()
    rule_controller = FakeController()
    install_named_entity_resolution_adapters(
        app_controller=app_controller,
        rule_controller=rule_controller,
    )
    rules = [
        {
            "id": 2844,
            "name": "Appliance: Fridge and Freezer - Auto ON",
            "normalised": "appliance fridge and freezer auto on",
        }
    ]
    intent = SimpleNamespace(
        requested_id="2844",
        variants=("fridge freezer rule", "fridge freezer"),
    )

    matches = rule_controller._exact_matches(rules, intent)

    assert [item["id"] for item in matches] == [2844]


def test_rule_adapter_returns_shortened_name_as_candidate_only():
    app_controller = FakeController()
    rule_controller = FakeController()
    install_named_entity_resolution_adapters(
        app_controller=app_controller,
        rule_controller=rule_controller,
    )
    rules = [
        {
            "id": 2844,
            "name": "Appliance: Fridge and Freezer - Auto ON",
            "normalised": "appliance fridge and freezer auto on",
        },
        {
            "id": 2967,
            "name": "Appliance: Fridge door left door",
            "normalised": "appliance fridge door left door",
        },
    ]
    intent = SimpleNamespace(
        requested_id=None,
        variants=("fridge freezer rule", "fridge freezer"),
    )

    exact = rule_controller._exact_matches(rules, intent)
    candidates = rule_controller._possible_matches(rules, intent)

    assert exact == []
    assert [item["id"] for item in candidates] == [2844]
