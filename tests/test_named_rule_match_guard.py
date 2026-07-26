from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from named_rule_match_guard import ranked_rule_candidates


def test_fridge_freezer_rule_finds_exact_inventory_candidate():
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

    candidates = ranked_rule_candidates(rules, ("fridge freezer rule", "fridge freezer"))

    assert [item["id"] for item in candidates] == [2844]


def test_broad_single_word_does_not_produce_unsafe_candidates():
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

    assert ranked_rule_candidates(rules, ("fridge",)) == []
