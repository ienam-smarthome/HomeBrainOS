from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from assistant_contracts import ResolutionStatus
from named_entity_resolver import NamedEntityResolver, records_from_rows


def test_exact_app_name_resolves_with_typed_entity_identity():
    resolver = NamedEntityResolver()
    entities = records_from_rows(
        [
            {
                "id": 3995,
                "name": "01. Humidity Controller",
                "normalised": "humidity controller",
            }
        ],
        "app",
    )

    result = resolver.resolve(entities, ("humidity controller app", "humidity controller"))

    assert result.status is ResolutionStatus.RESOLVED
    assert result.targets[0].entity_type == "app"
    assert result.targets[0].entity_id == "3995"
    assert result.targets[0].label == "01. Humidity Controller"


def test_shortened_rule_name_returns_safe_candidate_not_exact_write():
    resolver = NamedEntityResolver()
    entities = records_from_rows(
        [
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
        ],
        "rule",
    )

    result = resolver.resolve(entities, ("fridge freezer rule", "fridge freezer"))

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert [candidate.entity_id for candidate in result.candidates] == ["2844"]
    assert result.method == "ranked-candidates"


def test_broad_single_word_never_becomes_fuzzy_control_candidate():
    resolver = NamedEntityResolver()
    entities = records_from_rows(
        [
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
        ],
        "rule",
    )

    result = resolver.resolve(entities, ("fridge",))

    assert result.status is ResolutionStatus.NOT_FOUND
    assert result.candidates == []


def test_authoritative_entity_id_resolves_without_name_matching():
    resolver = NamedEntityResolver()
    entities = records_from_rows(
        [{"id": 3995, "name": "01. Humidity Controller", "normalised": "humidity controller"}],
        "app",
    )

    result = resolver.resolve(entities, (), exact_id="3995")

    assert result.status is ResolutionStatus.RESOLVED
    assert result.method == "exact-id"
    assert result.targets[0].entity_id == "3995"
