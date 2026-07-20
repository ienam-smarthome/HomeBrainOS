from __future__ import annotations

import re
from typing import Callable

import control_agent_claude_first
from control_agent_intent import (
    ControlActionIntent,
    ControlIntent,
    ControlTargetIntent,
)


_NUMBER_WORDS = {
    "one": 1,
    "first": 1,
    "two": 2,
    "second": 2,
    "three": 3,
    "third": 3,
    "four": 4,
    "fourth": 4,
    "five": 5,
    "fifth": 5,
    "six": 6,
    "sixth": 6,
    "seven": 7,
    "seventh": 7,
    "eight": 8,
    "eighth": 8,
    "nine": 9,
    "ninth": 9,
    "ten": 10,
    "tenth": 10,
}
_NUMBER_PATTERN = (
    r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2}(?:st|nd|rd|th)?)"
)
_TYPE_PATTERN = (
    r"(?:lights?|lamps?|bulbs?|dimmers?|fans?|switches?|sockets?|outlets?|plugs?|"
    r"dehumidifiers?|humidifiers?|televisions?|tvs?)"
)

_ORDINAL_BEFORE_TYPE = re.compile(
    rf"^(?P<room>.+?)\s+(?P<number>{_NUMBER_PATTERN})\s+(?P<type>{_TYPE_PATTERN})$",
    re.IGNORECASE,
)
_TYPE_BEFORE_ORDINAL = re.compile(
    rf"^(?P<room>.+?)\s+(?P<type>{_TYPE_PATTERN})\s+(?P<number>{_NUMBER_PATTERN})$",
    re.IGNORECASE,
)
_ORDINAL_PREFIX = re.compile(
    rf"^(?P<number>{_NUMBER_PATTERN})\s+(?P<room>.+?)\s+(?P<type>{_TYPE_PATTERN})$",
    re.IGNORECASE,
)

_TYPE_MAP = {
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "lamps": "light",
    "bulb": "light",
    "bulbs": "light",
    "dimmer": "light",
    "dimmers": "light",
    "fan": "fan",
    "fans": "fan",
    "switch": "switch",
    "switches": "switch",
    "socket": "outlet",
    "sockets": "outlet",
    "outlet": "outlet",
    "outlets": "outlet",
    "plug": "outlet",
    "plugs": "outlet",
    "dehumidifier": "dehumidifier",
    "dehumidifiers": "dehumidifier",
    "humidifier": "humidifier",
    "humidifiers": "humidifier",
    "television": "tv",
    "televisions": "tv",
    "tv": "tv",
    "tvs": "tv",
}
_TYPE_LABEL = {
    "light": "Light",
    "fan": "Fan",
    "switch": "Switch",
    "outlet": "Socket",
    "dehumidifier": "Dehumidifier",
    "humidifier": "Humidifier",
    "tv": "TV",
}
_ROOM_ALIASES = {
    "living room": "Living Room",
    "livingroom": "Living Room",
    "lounge": "Living Room",
    "bath room": "Bathroom",
    "bathroom": "Bathroom",
    "hall way": "Hallway",
    "hallway": "Hallway",
    "toilet": "Toilet",
    "kitchen": "Kitchen",
}


def _normalise(value: str) -> str:
    text = re.sub(r"[-_/]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip(" .!?")


def _number(value: str) -> int | None:
    text = _normalise(value).lower()
    if text in _NUMBER_WORDS:
        return _NUMBER_WORDS[text]
    match = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", text)
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 20 else None


def _room(value: str) -> str:
    text = _normalise(value)
    alias = _ROOM_ALIASES.get(text.lower())
    if alias:
        return alias
    return " ".join(part.capitalize() for part in text.split())


def decompose_natural_target(value: str) -> ControlTargetIntent:
    """Convert spoken room/number/type order into structured target fields.

    Numbered bedrooms are treated as room names because `Bedroom 1 Light` is a
    canonical household label. In non-numbered rooms, the number is an ordinal
    within the room, for example `living room one light` means the first light in
    Living Room.
    """

    target = _normalise(value)
    if not target:
        return ControlTargetIntent()

    match = (
        _ORDINAL_BEFORE_TYPE.match(target)
        or _TYPE_BEFORE_ORDINAL.match(target)
        or _ORDINAL_PREFIX.match(target)
    )
    if not match:
        return ControlTargetIntent(name_hint=target)

    number = _number(match.group("number"))
    raw_type = _normalise(match.group("type")).lower()
    device_type = _TYPE_MAP.get(raw_type, "")
    room_text = _normalise(match.group("room"))
    if number is None or not device_type or not room_text:
        return ControlTargetIntent(name_hint=target)

    # `bedroom one light` names the numbered room and its canonical light. This
    # remains exact even when Bedroom 3 contains additional lamps.
    if room_text.lower() in {"bedroom", "bed room"}:
        room_hint = f"Bedroom {number}"
        name_hint = f"{room_hint} {_TYPE_LABEL.get(device_type, raw_type.title())}"
        return ControlTargetIntent(
            name_hint=name_hint,
            room_hint=room_hint,
            device_type=device_type,
        )

    return ControlTargetIntent(
        room_hint=_room(room_text),
        device_type=device_type,
        ordinal=number,
    )


def install_semantic_natural_targets() -> None:
    """Upgrade natural level intents before they reach device resolution."""

    if getattr(control_agent_claude_first, "_semantic_target_installed", False):
        return

    original: Callable[[str], ControlIntent | None] = (
        control_agent_claude_first.parse_natural_level
    )

    def parse_with_semantic_target(query: str) -> ControlIntent | None:
        intent = original(query)
        if intent is None:
            return None

        actions: list[ControlActionIntent] = []
        changed = False
        for action in intent.actions:
            target = action.target
            if action.command == "set_level" and target.name_hint:
                semantic = decompose_natural_target(target.name_hint)
                if semantic != target:
                    target = semantic
                    changed = True
            actions.append(
                ControlActionIntent(
                    command=action.command,
                    value=action.value,
                    target=target,
                )
            )

        if not changed:
            return intent
        return ControlIntent(
            intent=intent.intent,
            actions=tuple(actions),
            confidence=intent.confidence,
            interpreter="deterministic-semantic-control-parser",
            model=intent.model,
        )

    control_agent_claude_first.parse_natural_level = parse_with_semantic_target
    control_agent_claude_first._semantic_target_installed = True


__all__ = ["decompose_natural_target", "install_semantic_natural_targets"]
