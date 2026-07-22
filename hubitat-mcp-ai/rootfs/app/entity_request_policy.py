from __future__ import annotations
import re
from dataclasses import asdict, dataclass
from typing import Any
from entity_resolution import infer_ordinal, normalise_text

_BROAD_PATTERNS = (
    r"(?:show|list|find|search|display|get) (?:all )?(?:my |the )?devices(?: in .+)?",
    r"(?:what|which) devices (?:are|do|have|need|in|on|off).+",
    r"devices in (?:the )?.+",
)
_PREFIX = re.compile(r"^(?:please )?(?:(?:turn|switch|set|dim|open|close|lock|unlock|find|locate|show|read|check|get)\s+|what(?:'s| is)\s+)(?:the )?", re.I)
_TRAILING = re.compile(r"\s+(?:on|off|state|status|level|power|temperature|humidity)(?:\s+now)?$", re.I)
_ROOM = re.compile(r"\b(?:in|from)\s+(?:the )?([a-z0-9 -]+?)(?:\s+room)?$", re.I)

@dataclass(frozen=True)
class EntityRequest:
    query: str
    target_phrase: str
    room: str | None = None
    device_type: str | None = None
    ordinal: int | None = None
    broad_inventory: bool = False
    targeted: bool = False
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

def _device_type(value: str) -> str | None:
    q = normalise_text(value)
    aliases = {
        "light": ("light", "lamp", "bulb", "dimmer"),
        "fan": ("fan", "ventilation"),
        "switch": ("switch", "socket", "plug", "outlet"),
        "thermostat": ("thermostat", "trv", "radiator"),
        "contact": ("contact", "door", "window"),
        "motion": ("motion", "presence", "occupancy"),
        "lock": ("lock",),
    }
    for canonical, terms in aliases.items():
        if any(re.search(rf"\b{re.escape(term)}\b", q) for term in terms):
            return canonical
    return None

def parse_entity_request(query: str) -> EntityRequest:
    q = normalise_text(query).strip(" .!?")
    broad = any(re.fullmatch(pattern, q) for pattern in _BROAD_PATTERNS)
    room_match = _ROOM.search(q)
    room = normalise_text(room_match.group(1)) if room_match else None
    target = _TRAILING.sub("", _PREFIX.sub("", q))
    target = re.sub(r"\b(?:to|at)\s+\d+(?:\s*%)?$", "", target).strip()
    if room_match and room_match.start() > 0:
        target = target[:room_match.start()].strip()
    target = re.sub(r"^(?:a|an|the)\s+", "", target).strip()
    useful = bool(target and target not in {"device", "devices", "all devices"})
    return EntityRequest(q, target, room, _device_type(target or q), infer_ordinal(target or q), broad, useful and not broad)

def is_targeted_device_request(query: str) -> bool:
    return parse_entity_request(query).targeted

__all__ = ["EntityRequest", "is_targeted_device_request", "parse_entity_request"]
