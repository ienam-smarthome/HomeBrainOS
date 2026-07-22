from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Iterable


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    RESOLVED_GROUP = "resolved_group"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    UNSUPPORTED_ACTION = "unsupported_action"


@dataclass(frozen=True)
class ResolutionRequest:
    target_phrase: str
    action: str | None = None
    room: str | None = None
    device_type: str | None = None
    ordinal: int | None = None
    allow_group: bool = False
    limit: int = 6


@dataclass(frozen=True)
class ResolvedTarget:
    device_id: str
    label: str
    room: str | None
    score: float
    match_reasons: tuple[str, ...] = ()
    supported: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolutionResult:
    status: ResolutionStatus
    confidence: float
    targets: tuple[ResolvedTarget, ...] = ()
    candidates: tuple[ResolvedTarget, ...] = ()
    reason: str = ""
    query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved(self) -> bool:
        return self.status in {ResolutionStatus.RESOLVED, ResolutionStatus.RESOLVED_GROUP}

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "confidence": round(self.confidence, 3),
            "targets": [item.as_dict() for item in self.targets],
            "candidates": [item.as_dict() for item in self.candidates],
            "reason": self.reason,
            "query": self.query,
            "metadata": dict(self.metadata),
        }


_ROOM_ALIASES = {
    "livingroom": "living room",
    "living room": "living room",
    "hall": "hallway",
    "hallway": "hallway",
    "bedroom1": "bedroom 1",
    "bed room 1": "bedroom 1",
    "bedroom2": "bedroom 2",
    "bed room 2": "bedroom 2",
    "bedroom3": "bedroom 3",
    "bed room 3": "bedroom 3",
}

_TYPE_ALIASES = {
    "light": {"light", "lamp", "bulb", "dimmer"},
    "switch": {"switch", "socket", "plug", "outlet"},
    "fan": {"fan", "ventilation"},
    "thermostat": {"thermostat", "trv", "radiator", "heating"},
    "contact": {"contact", "door", "window"},
    "motion": {"motion", "occupancy", "presence"},
    "lock": {"lock"},
}

_ACTION_CAPABILITIES = {
    "on": {"switch", "switchlevel"},
    "off": {"switch", "switchlevel"},
    "set_level": {"switchlevel"},
    "dim": {"switchlevel"},
    "set_heating": {"thermostat", "thermostatheatingsetpoint"},
    "lock": {"lock"},
    "unlock": {"lock"},
    "open": {"doorcontrol", "windowshade", "valve"},
    "close": {"doorcontrol", "windowshade", "valve"},
}

_STOP_WORDS = {
    "the", "a", "an", "please", "device", "devices", "turn", "switch", "set",
    "to", "at", "on", "off", "in", "from", "room", "my", "this", "that",
}

_ORDINAL_WORDS = {
    "first": 1,
    "1st": 1,
    "one": 1,
    "second": 2,
    "2nd": 2,
    "two": 2,
    "third": 3,
    "3rd": 3,
    "three": 3,
    "fourth": 4,
    "4th": 4,
    "four": 4,
}


def normalise_text(value: Any) -> str:
    text = str(value or "").lower().replace("_", " ")
    text = re.sub(r"\bbed\s*room\b", "bedroom", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for alias, canonical in sorted(_ROOM_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(rf"\b{re.escape(alias)}\b", canonical, text)
    return text


def compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", normalise_text(value))


def _tokens(value: Any) -> set[str]:
    return {token for token in normalise_text(value).split() if token and token not in _STOP_WORDS}


def _device_label(device: dict[str, Any]) -> str:
    return str(device.get("label") or device.get("name") or device.get("id") or "Unknown device")


def _device_room(device: dict[str, Any]) -> str | None:
    room = device.get("room") or device.get("roomName") or device.get("room_name")
    return str(room).strip() if room not in (None, "") else None


def _capability_names(device: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in device.get("capabilities") or []:
        if isinstance(item, dict):
            value = item.get("name") or item.get("displayName") or item.get("id")
        else:
            value = item
        if value:
            names.add(compact(value))
    for command in device.get("commands") or []:
        value = command.get("command") or command.get("name") if isinstance(command, dict) else command
        if value:
            names.add(compact(value))
    attrs = device.get("attributes") or {}
    if isinstance(attrs, dict):
        names.update(compact(key) for key in attrs)
    return names


def supports_action(device: dict[str, Any], action: str | None) -> bool:
    if not action:
        return True
    required = _ACTION_CAPABILITIES.get(normalise_text(action).replace(" ", "_"))
    if not required:
        return True
    names = _capability_names(device)
    return bool(names & required)


def infer_ordinal(value: str) -> int | None:
    q = normalise_text(value)
    for word, number in _ORDINAL_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", q):
            return number
    match = re.search(r"\b([1-9])\b", q)
    return int(match.group(1)) if match else None


def _type_matches(device: dict[str, Any], requested_type: str | None) -> bool:
    if not requested_type:
        return True
    requested = normalise_text(requested_type)
    terms = _TYPE_ALIASES.get(requested, {requested})
    haystack = normalise_text(" ".join([
        _device_label(device),
        _device_room(device) or "",
        str(device.get("category") or ""),
        " ".join(_capability_names(device)),
    ]))
    return any(term in haystack for term in terms)


def _score_device(device: dict[str, Any], request: ResolutionRequest) -> ResolvedTarget:
    label = _device_label(device)
    label_n = normalise_text(label)
    label_c = compact(label)
    target_n = normalise_text(request.target_phrase)
    target_c = compact(request.target_phrase)
    room = _device_room(device)
    room_n = normalise_text(room)
    requested_room = normalise_text(request.room)
    reasons: list[str] = []
    score = 0.0

    if target_c and target_c == label_c:
        score += 1.0
        reasons.append("exact label")
    elif target_n and target_n == label_n:
        score += 0.98
        reasons.append("normalised exact label")
    elif target_c and (target_c in label_c or label_c in target_c):
        score += 0.72
        reasons.append("label containment")

    target_tokens = _tokens(target_n)
    label_tokens = _tokens(label_n)
    if target_tokens and label_tokens:
        overlap = len(target_tokens & label_tokens) / max(len(target_tokens), 1)
        if overlap:
            score += 0.48 * overlap
            reasons.append(f"token overlap {overlap:.2f}")

    if target_c and label_c:
        similarity = SequenceMatcher(None, target_c, label_c).ratio()
        if similarity >= 0.60:
            score += 0.30 * similarity
            reasons.append(f"fuzzy label {similarity:.2f}")

    if requested_room:
        if requested_room == room_n:
            score += 0.32
            reasons.append("exact room")
        elif compact(requested_room) and compact(requested_room) == compact(room_n):
            score += 0.28
            reasons.append("normalised room")
        else:
            score -= 0.25
            reasons.append("room mismatch")
    elif room_n and room_n in target_n:
        score += 0.20
        reasons.append("room named in target")

    if request.device_type:
        if _type_matches(device, request.device_type):
            score += 0.18
            reasons.append("device type")
        else:
            score -= 0.35
            reasons.append("device type mismatch")

    ordinal = request.ordinal or infer_ordinal(request.target_phrase)
    if ordinal is not None:
        label_ordinal = infer_ordinal(label)
        if label_ordinal == ordinal:
            score += 0.26
            reasons.append("ordinal")
        elif label_ordinal is not None:
            score -= 0.24
            reasons.append("ordinal mismatch")

    supported = supports_action(device, request.action)
    if supported:
        if request.action:
            score += 0.10
            reasons.append("supports action")
    else:
        score -= 0.55
        reasons.append("unsupported action")

    return ResolvedTarget(
        device_id=str(device.get("id") or ""),
        label=label,
        room=room,
        score=round(max(0.0, min(score, 1.5)), 4),
        match_reasons=tuple(reasons),
        supported=supported,
    )


def resolve_devices(devices: Iterable[dict[str, Any]], request: ResolutionRequest) -> ResolutionResult:
    candidates = [
        _score_device(device, request)
        for device in devices
        if isinstance(device, dict) and device.get("id") not in (None, "")
    ]
    candidates.sort(key=lambda item: (-item.score, item.label.lower(), item.device_id))
    candidates = candidates[: max(1, request.limit)]
    supported = [item for item in candidates if item.supported]

    if not candidates or candidates[0].score < 0.48:
        return ResolutionResult(
            status=ResolutionStatus.NOT_FOUND,
            confidence=0.0 if not candidates else candidates[0].score,
            candidates=tuple(candidates),
            reason="No candidate reached the minimum resolution score.",
            query=request.target_phrase,
        )

    if not supported:
        return ResolutionResult(
            status=ResolutionStatus.UNSUPPORTED_ACTION,
            confidence=candidates[0].score,
            candidates=tuple(candidates),
            reason="Matching devices do not support the requested action.",
            query=request.target_phrase,
        )

    best = supported[0]
    close = [item for item in supported if best.score - item.score <= 0.10 and item.score >= 0.58]

    if request.allow_group and len(close) > 1:
        return ResolutionResult(
            status=ResolutionStatus.RESOLVED_GROUP,
            confidence=min(item.score for item in close),
            targets=tuple(close),
            candidates=tuple(candidates),
            reason="Multiple closely matching devices were intentionally resolved as a group.",
            query=request.target_phrase,
        )

    if len(close) > 1:
        return ResolutionResult(
            status=ResolutionStatus.AMBIGUOUS,
            confidence=best.score,
            candidates=tuple(close),
            reason="Multiple devices have similarly strong matches.",
            query=request.target_phrase,
        )

    return ResolutionResult(
        status=ResolutionStatus.RESOLVED,
        confidence=best.score,
        targets=(best,),
        candidates=tuple(candidates),
        reason="A single supported device is the strongest match.",
        query=request.target_phrase,
    )


__all__ = [
    "ResolutionRequest",
    "ResolutionResult",
    "ResolutionStatus",
    "ResolvedTarget",
    "compact",
    "infer_ordinal",
    "normalise_text",
    "resolve_devices",
    "supports_action",
]
