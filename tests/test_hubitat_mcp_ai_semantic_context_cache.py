from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from semantic_read_intent import SemanticReadIntentClassifier  # noqa: E402


def test_cache_key_includes_recent_conversation_context():
    query = "Which one is highest?"
    power_history = [
        {"role": "user", "content": "Show the power readings"},
        {"role": "assistant", "content": "Freezer 72 W, Computer 50 W"},
    ]
    temperature_history = [
        {"role": "user", "content": "Show the room temperatures"},
        {"role": "assistant", "content": "Bedroom 22 C, Living Room 25 C"},
    ]

    assert SemanticReadIntentClassifier._cache_key(query, power_history) != (
        SemanticReadIntentClassifier._cache_key(query, temperature_history)
    )


def test_cache_key_is_stable_for_equivalent_whitespace():
    application = SimpleNamespace(option_bool=lambda *_: False)
    classifier = SemanticReadIntentClassifier(application)

    first = classifier._cache_key(
        " Which   device is highest? ",
        [{"role": "user", "content": " Power   readings "}],
    )
    second = classifier._cache_key(
        "which device is highest?",
        [{"role": "user", "content": "power readings"}],
    )

    assert first == second


def test_bottom_ranking_fallback_preserves_minimum_direction():
    parsed = SemanticReadIntentClassifier._deterministic_fallback(
        "Show the bottom 3 battery devices"
    )

    assert parsed is not None
    assert parsed.metric == "battery"
    assert parsed.operation == "min"
    assert parsed.top_n == 3
