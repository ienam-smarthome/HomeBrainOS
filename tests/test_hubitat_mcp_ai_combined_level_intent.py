from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "hubitat-mcp-ai" / "rootfs" / "app"
sys.path.insert(0, str(APP_DIR))

from control_agent_combined_level import install_combined_level_intent  # noqa: E402
from control_agent_gate import is_exact_fast_control  # noqa: E402
from control_agent_intent import ControlIntentInterpreter  # noqa: E402


class FakeApplication:
    ollama = SimpleNamespace()

    @staticmethod
    def option_bool(_name: str, default: bool = False) -> bool:
        return default


def parse(query: str):
    install_combined_level_intent()
    return ControlIntentInterpreter(FakeApplication())._deterministic_intent(query)


def assert_level(query: str, *, target: str, value: float):
    intent = parse(query)

    assert intent is not None
    assert intent.model is None
    assert intent.interpreter == "deterministic-control-parser"
    assert len(intent.actions) == 1
    action = intent.actions[0]
    assert action.command == "set_level"
    assert action.value == value
    assert action.target.name_hint == target
    return intent


def test_turn_on_device_to_level_becomes_one_set_level_action():
    assert_level(
        "turn on Bedroom 1 Light to 30%",
        target="Bedroom 1 Light",
        value=30,
    )


def test_turn_on_device_at_level_is_an_exact_fast_control():
    query = "turn on living room light 2 at 90%"

    assert_level(query, target="living room light 2", value=90)
    assert is_exact_fast_control(query) is True


def test_numbered_device_name_is_not_mistaken_for_level_syntax():
    assert_level(
        "switch on bathroom light 12 to 35 percent",
        target="bathroom light 12",
        value=35,
    )


def test_turn_device_on_at_level_alternate_word_order_is_supported():
    assert_level(
        "turn Bedroom 1 Light on at 45 percent",
        target="Bedroom 1 Light",
        value=45,
    )


def test_absolute_set_at_level_strips_at_from_exact_device_name():
    intent = assert_level(
        "set Bedroom 1 Light at 30%",
        target="Bedroom 1 Light",
        value=30,
    )

    assert intent.actions[0].target.name_hint != "Bedroom 1 Light at"


def test_absolute_set_to_level_strips_to_from_exact_device_name():
    assert_level(
        "set the Bedroom 1 Light to 35 percent",
        target="Bedroom 1 Light",
        value=35,
    )


def test_bare_absolute_level_remains_supported_without_preposition():
    assert_level(
        "dim Bedroom 1 Light 40%",
        target="Bedroom 1 Light",
        value=40,
    )


def test_combined_level_does_not_include_percentage_in_device_name():
    intent = assert_level(
        "switch on the Bedroom 1 Light to 25%",
        target="Bedroom 1 Light",
        value=25,
    )

    assert "25" not in intent.actions[0].target.name_hint


def test_out_of_range_level_is_not_clamped_or_deterministically_executed():
    assert parse("turn on Bedroom 1 Light to 130%") is None
    assert parse("set Bedroom 1 Light to 130%") is None
    assert parse("set Bedroom 1 Light at 130%") is None


def test_contextual_combined_level_still_requires_structured_context():
    assert parse("turn it on to 30%") is None


def test_malformed_repeated_preposition_does_not_create_fake_device_name():
    assert parse("set Bedroom 1 Light at at 30%") is None
    assert parse("set Bedroom 1 Light to to 30%") is None


def test_entrypoint_installs_combined_parser_before_control_agent():
    entrypoint = (APP_DIR / "entrypoint.py").read_text(encoding="utf-8")

    assert "from control_agent_combined_level import install_combined_level_intent" in entrypoint
    assert entrypoint.index("install_combined_level_intent()") < entrypoint.index(
        "control_agent = install_control_agent("
    )
