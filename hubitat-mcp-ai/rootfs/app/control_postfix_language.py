from __future__ import annotations

import re
from dataclasses import dataclass


_POSTFIX_CONTROL = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+(?:the\s+)?(.+?)\s+(on|off)[.!?]*$",
    re.IGNORECASE,
)
_PREFIX_CONTROL = re.compile(
    r"^(?:please\s+)?(?:turn|switch)\s+(on|off)\s+(?:the\s+)?(.+?)[.!?]*$",
    re.IGNORECASE,
)
_ORDINAL_PREFIX = re.compile(
    r"^(?:number\s+)?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2}(?:st|nd|rd|th)?)\s+(.+)$",
    re.IGNORECASE,
)
_DEVICE_TYPE_SUFFIX = re.compile(
    r"^(.+?)(?:\s+)(lights?|lamps?|bulbs?|dimmers?|fans?|switches?|sockets?|"
    r"outlets?|plugs?|dehumidifiers?|humidifiers?|televisions?|tvs?)$",
    re.IGNORECASE,
)
_CONTEXT_WORDS = {
    "all",
    "every",
    "both",
    "other",
    "same",
    "it",
    "them",
    "those",
    "these",
    "that",
    "one",
    "ones",
    "back",
}
_ORDINALS = {
    "first": 1,
    "one": 1,
    "second": 2,
    "two": 2,
    "third": 3,
    "three": 3,
    "fourth": 4,
    "four": 4,
    "fifth": 5,
    "five": 5,
    "sixth": 6,
    "six": 6,
    "seventh": 7,
    "seven": 7,
    "eighth": 8,
    "eight": 8,
    "ninth": 9,
    "nine": 9,
    "tenth": 10,
    "ten": 10,
}
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
_ROOM_ALIASES = {
    "lounge": "Living Room",
    "living room": "Living Room",
    "livingroom": "Living Room",
}


@dataclass(frozen=True, slots=True)
class PostfixControlPhrase:
    action: str
    name_hint: str = ""
    room_hint: str = ""
    device_type: str = ""
    ordinal: int | None = None


def _normalise_phrase(value: str) -> str:
    text = re.sub(r"[-_/]+", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip(" .!?")


def _ordinal(value: str) -> int | None:
    text = str(value or "").strip().lower()
    if text in _ORDINALS:
        return _ORDINALS[text]
    match = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", text)
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 20 else None


def parse_postfix_control(query: str) -> PostfixControlPhrase | None:
    """Parse ordinal controls with the action before or after the target.

    Examples:
      - ``switch Bedroom 1 Light off`` -> exact device name
      - ``switch the second living-room light off`` -> room/type/ordinal
      - ``turn off the second hallway light`` -> room/type/ordinal

    Contextual and group phrases deliberately return ``None`` so they remain on the
    structured context/AI path rather than being treated as a single device.
    """

    text = str(query or "").strip()
    match = _POSTFIX_CONTROL.match(text)
    prefix_form = False
    if match:
        target = _normalise_phrase(match.group(1))
        action = str(match.group(2) or "").lower()
    else:
        prefix = _PREFIX_CONTROL.match(text)
        if prefix is None:
            return None
        prefix_form = True
        action = str(prefix.group(1) or "").lower()
        target = _normalise_phrase(prefix.group(2))

    if not target or action not in {"on", "off"}:
        return None
    words = set(re.findall(r"[a-z0-9]+", target.lower()))
    if not target or words.intersection(_CONTEXT_WORDS):
        return None

    ordinal_match = _ORDINAL_PREFIX.match(target)
    if ordinal_match:
        ordinal = _ordinal(ordinal_match.group(1))
        descriptor = _normalise_phrase(ordinal_match.group(2))
        type_match = _DEVICE_TYPE_SUFFIX.match(descriptor)
        if ordinal is None or not type_match:
            return None
        room_text = _normalise_phrase(type_match.group(1))
        raw_type = str(type_match.group(2) or "").lower()
        device_type = _TYPE_MAP.get(raw_type, "")
        if not device_type:
            return None
        room_hint = _ROOM_ALIASES.get(room_text.lower(), room_text)
        return PostfixControlPhrase(
            action=action,
            room_hint=room_hint,
            device_type=device_type,
            ordinal=ordinal,
        )

    # Prefix action grammar already belongs to the base deterministic parser.
    # This extension only adds the missing structured ordinal form; refusing all
    # other prefix targets prevents multi-device and conditional requests from
    # being flattened into one apparent device name.
    if prefix_form:
        return None
    return PostfixControlPhrase(action=action, name_hint=target)


__all__ = ["PostfixControlPhrase", "parse_postfix_control"]
