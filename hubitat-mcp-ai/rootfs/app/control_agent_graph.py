from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from control_agent_intent import ControlTargetIntent
from device_intelligence_index import (
    DeviceIntelligenceIndex,
    _attributes,
    _device_id,
    _label,
    _looks_like_light,
    _looks_like_outlet,
    _normalise,
    _room_name,
)
from spoken_device_name import spoken_name_key


_ORDINAL_WORDS = {
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
    6: "sixth",
    7: "seventh",
    8: "eighth",
    9: "ninth",
    10: "tenth",
}
_TYPE_SYNONYMS = {
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "lamps": "light",
    "bulb": "light",
    "bulbs": "light",
    "dimmer": "light",
    "fan": "fan",
    "fans": "fan",
    "socket": "outlet",
    "sockets": "outlet",
    "outlet": "outlet",
    "outlets": "outlet",
    "plug": "outlet",
    "plugs": "outlet",
    "switch": "switch",
    "switches": "switch",
    "dehumidifier": "dehumidifier",
    "humidifier": "humidifier",
    "television": "tv",
    "tv": "tv",
    "camera": "camera",
    "thermostat": "thermostat",
    "trv": "thermostat",
    "lock": "lock",
    "alarm": "alarm",
    "valve": "valve",
    "door": "door",
    "heater": "heater",
}
_SENSITIVE_TYPES = {"lock", "alarm", "valve", "door", "thermostat", "heater"}


@dataclass(slots=True)
class DeviceNode:
    id: str
    label: str
    room: str
    types: set[str]
    aliases: set[str]
    ordinal: int | None
    current_states: dict[str, Any]
    raw: dict[str, Any]

    @property
    def risk(self) -> str:
        return "sensitive" if self.types & _SENSITIVE_TYPES else "low"

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "room": self.room,
            "types": sorted(self.types),
            "ordinal": self.ordinal,
            "risk": self.risk,
        }


@dataclass(slots=True)
class GraphContext:
    last_device_ids: tuple[str, ...] = ()
    last_candidate_ids: tuple[str, ...] = ()
    last_room: str = ""
    last_device_type: str = ""


@dataclass(slots=True)
class DeviceResolution:
    nodes: list[DeviceNode] = field(default_factory=list)
    candidates: list[DeviceNode] = field(default_factory=list)
    confidence: float = 0.0
    method: str = "unresolved"
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return bool(self.nodes)

    @property
    def ambiguous(self) -> bool:
        return not self.nodes and len(self.candidates) > 1


class ControlDeviceGraph:
    """Selected-device knowledge graph for deterministic control resolution."""

    def __init__(
        self,
        devices: Iterable[dict[str, Any]],
        *,
        learned_aliases: dict[str, str] | None = None,
    ) -> None:
        self.nodes = self._build_nodes(list(devices), learned_aliases or {})
        self.by_id = {item.id: item for item in self.nodes}
        self._alias_index: dict[str, list[DeviceNode]] = {}
        for node in self.nodes:
            for alias in node.aliases:
                key = spoken_name_key(alias)
                if key:
                    self._alias_index.setdefault(key, []).append(node)

    def inventory_summary(self, *, max_chars: int = 5000) -> str:
        rows = [
            f"{node.label} | {node.room or 'No room'} | {','.join(sorted(node.types)) or 'device'}"
            for node in sorted(self.nodes, key=lambda item: (item.room.lower(), item.label.lower()))
        ]
        text = "\n".join(rows)
        return text[:max_chars]

    def resolve(
        self,
        target: ControlTargetIntent,
        *,
        context: GraphContext | None = None,
    ) -> DeviceResolution:
        context = context or GraphContext()
        reference = target.reference
        if reference != "none":
            referenced = self._resolve_reference(reference, context)
            if referenced:
                return DeviceResolution(
                    nodes=referenced,
                    candidates=referenced,
                    confidence=0.98,
                    method=f"context-{reference}",
                    reason="Resolved from structured conversation context.",
                )
            return DeviceResolution(
                confidence=0.0,
                method=f"context-{reference}-missing",
                reason="The requested conversation reference is no longer available.",
            )

        exact = self._exact_alias(target.name_hint)
        if len(exact) == 1 and target.quantifier == "one":
            node = exact[0]
            if self._matches_constraints(node, target):
                return DeviceResolution(
                    nodes=[node],
                    candidates=[node],
                    confidence=1.0,
                    method="unique-alias",
                    reason="One selected device owns the exact spoken alias.",
                )
        if len(exact) > 1 and target.quantifier == "one":
            constrained = [item for item in exact if self._matches_constraints(item, target)]
            if len(constrained) == 1:
                return DeviceResolution(
                    nodes=constrained,
                    candidates=constrained,
                    confidence=0.97,
                    method="alias-plus-constraints",
                    reason="Room/type constraints made the spoken alias unique.",
                )
            return DeviceResolution(
                candidates=constrained or exact,
                confidence=0.45,
                method="ambiguous-alias",
                reason="More than one selected device owns the spoken alias.",
            )

        filtered = [item for item in self.nodes if self._matches_constraints(item, target)]
        filtered = self._apply_exclusions(filtered, target.exclusions)

        if target.quantifier == "all":
            if not filtered:
                return DeviceResolution(
                    confidence=0.0,
                    method="group-not-found",
                    reason="No selected devices matched the requested room/type group.",
                )
            return DeviceResolution(
                nodes=filtered,
                candidates=filtered,
                confidence=0.94 if target.room_hint or target.device_type else 0.72,
                method="room-type-group",
                reason="All selected devices matching the structured room/type constraints were resolved.",
            )

        if target.ordinal is not None:
            ordinal_matches = [item for item in filtered if item.ordinal == target.ordinal]
            if len(ordinal_matches) == 1:
                return DeviceResolution(
                    nodes=ordinal_matches,
                    candidates=ordinal_matches,
                    confidence=0.98,
                    method="room-type-ordinal",
                    reason="Room, type and ordinal identify one selected device.",
                )
            if ordinal_matches:
                return DeviceResolution(
                    candidates=ordinal_matches,
                    confidence=0.45,
                    method="ambiguous-ordinal",
                    reason="The ordinal still matches more than one selected device.",
                )

        if len(filtered) == 1:
            return DeviceResolution(
                nodes=filtered,
                candidates=filtered,
                confidence=0.92,
                method="unique-structured-target",
                reason="The structured room/type/name constraints identify one selected device.",
            )
        if len(filtered) > 1:
            ranked = self._rank_name_hint(target.name_hint, filtered)
            if ranked and ranked[0][0] >= 0.88:
                top_score = ranked[0][0]
                top = [item for score, item in ranked if abs(score - top_score) < 0.02]
                if len(top) == 1:
                    return DeviceResolution(
                        nodes=top,
                        candidates=[item for _, item in ranked[:5]],
                        confidence=min(0.95, top_score),
                        method="unique-name-score",
                        reason="One selected candidate strongly matched the structured name hint.",
                    )
            return DeviceResolution(
                candidates=[item for _, item in ranked[:5]] if ranked else filtered[:5],
                confidence=0.4,
                method="ambiguous-structured-target",
                reason="Several selected devices match the requested constraints.",
            )

        nearby = self._rank_name_hint(target.name_hint, self.nodes)
        return DeviceResolution(
            candidates=[item for score, item in nearby[:5] if score >= 0.25],
            confidence=0.0,
            method="target-not-found",
            reason="No selected device matched all structured constraints.",
        )

    def _resolve_reference(self, reference: str, context: GraphContext) -> list[DeviceNode]:
        ids: tuple[str, ...] = ()
        if reference == "last":
            ids = context.last_device_ids[-1:]
        elif reference == "both":
            ids = context.last_device_ids or context.last_candidate_ids
        elif reference == "other":
            group = context.last_candidate_ids or context.last_device_ids
            last = context.last_device_ids[-1] if context.last_device_ids else ""
            ids = tuple(item for item in group if item != last)
        return [self.by_id[item] for item in ids if item in self.by_id]

    def _exact_alias(self, value: str) -> list[DeviceNode]:
        key = spoken_name_key(value)
        return list(self._alias_index.get(key, [])) if key else []

    def _matches_constraints(self, node: DeviceNode, target: ControlTargetIntent) -> bool:
        if target.room_hint and not self._room_matches(target.room_hint, node.room):
            return False
        wanted_type = self._canonical_type(target.device_type)
        if wanted_type and wanted_type not in node.types:
            return False
        if target.ordinal is not None and node.ordinal != target.ordinal:
            return False
        if target.name_hint:
            key = spoken_name_key(target.name_hint)
            if key and key in self._alias_index:
                return node in self._alias_index[key]
            terms = self._meaningful_terms(target.name_hint)
            if terms:
                searchable = self._meaningful_terms(f"{node.label} {node.room} {' '.join(node.types)}")
                if not terms.issubset(searchable):
                    return False
        return True

    @staticmethod
    def _room_matches(requested: str, actual: str) -> bool:
        wanted = spoken_name_key(requested)
        current = spoken_name_key(actual)
        if not wanted:
            return True
        return wanted == current or wanted in current or current in wanted

    @staticmethod
    def _canonical_type(value: str) -> str:
        normal = _normalise(value)
        if not normal:
            return ""
        return _TYPE_SYNONYMS.get(normal, _TYPE_SYNONYMS.get(normal.rstrip("s"), normal.rstrip("s")))

    @classmethod
    def _apply_exclusions(
        cls,
        nodes: list[DeviceNode],
        exclusions: tuple[str, ...],
    ) -> list[DeviceNode]:
        if not exclusions:
            return nodes
        excluded_keys = [spoken_name_key(item) for item in exclusions if spoken_name_key(item)]
        return [
            node
            for node in nodes
            if not any(
                key == spoken_name_key(node.label)
                or key in spoken_name_key(node.label)
                or key in {spoken_name_key(alias) for alias in node.aliases}
                for key in excluded_keys
            )
        ]

    @staticmethod
    def _meaningful_terms(value: str) -> set[str]:
        ignored = {
            "the",
            "a",
            "an",
            "please",
            "device",
            "one",
            "first",
            "second",
            "third",
            "fourth",
            "all",
        }
        return {
            _TYPE_SYNONYMS.get(word, word)
            for word in _normalise(value).split()
            if word and word not in ignored and not word.isdigit()
        }

    @classmethod
    def _rank_name_hint(
        cls,
        hint: str,
        nodes: list[DeviceNode],
    ) -> list[tuple[float, DeviceNode]]:
        terms = cls._meaningful_terms(hint)
        key = spoken_name_key(hint)
        ranked: list[tuple[float, DeviceNode]] = []
        for node in nodes:
            alias_keys = {spoken_name_key(item) for item in node.aliases}
            if key and key in alias_keys:
                score = 1.0
            else:
                node_terms = cls._meaningful_terms(f"{node.label} {node.room} {' '.join(node.types)}")
                overlap = len(terms & node_terms) / max(1, len(terms | node_terms)) if terms else 0.0
                containment = 0.2 if key and any(key in item or item in key for item in alias_keys) else 0.0
                score = overlap + containment
            ranked.append((score, node))
        ranked.sort(key=lambda item: (-item[0], item[1].label.lower()))
        return ranked

    @classmethod
    def _build_nodes(
        cls,
        devices: list[dict[str, Any]],
        learned_aliases: dict[str, str],
    ) -> list[DeviceNode]:
        provisional: list[DeviceNode] = []
        for raw in devices:
            device_id = _device_id(raw)
            label = _label(raw)
            if not device_id or not label or bool(raw.get("disabled")):
                continue
            room = _room_name(raw)
            types = set(DeviceIntelligenceIndex._infer_groups(raw))
            normal_label = " " + _normalise(label) + " "
            for word, canonical in _TYPE_SYNONYMS.items():
                if f" {word} " in normal_label:
                    types.add(canonical)
            if _looks_like_light(raw):
                types.add("light")
            if _looks_like_outlet(raw):
                types.add("outlet")
            if " tv " in normal_label or " television " in normal_label:
                types.add("tv")
            number_match = re.search(r"(?:^|\s)(\d{1,2})(?:\s|$)", _normalise(label))
            ordinal = int(number_match.group(1)) if number_match else None
            aliases = {label}
            if room:
                aliases.add(f"{room} {label}")
            base = re.sub(r"\s*(?:\([^)]*\)|\[[^]]*\])\s*$", "", label).strip()
            if base:
                aliases.add(base)
            for alias, target_label in learned_aliases.items():
                if spoken_name_key(target_label) == spoken_name_key(label):
                    aliases.add(alias)
            provisional.append(
                DeviceNode(
                    id=device_id,
                    label=label,
                    room=room,
                    types=types,
                    aliases=aliases,
                    ordinal=ordinal,
                    current_states=_attributes(raw),
                    raw=raw,
                )
            )

        groups: dict[tuple[str, str], list[DeviceNode]] = {}
        for node in provisional:
            for device_type in sorted(node.types):
                if device_type in {"device", "switch", "sensor"}:
                    continue
                groups.setdefault((spoken_name_key(node.room), device_type), []).append(node)
        for (_room, device_type), nodes in groups.items():
            nodes.sort(key=lambda item: (item.ordinal if item.ordinal is not None else 999, item.label.lower()))
            for index, node in enumerate(nodes, start=1):
                if node.ordinal is None:
                    node.ordinal = index
                room = node.room
                if room:
                    node.aliases.add(f"{room} {device_type} {node.ordinal}")
                    node.aliases.add(f"{_ORDINAL_WORDS.get(node.ordinal, str(node.ordinal))} {room} {device_type}")
                    node.aliases.add(f"{room} {_ORDINAL_WORDS.get(node.ordinal, str(node.ordinal))} {device_type}")
        return provisional


__all__ = [
    "ControlDeviceGraph",
    "DeviceNode",
    "DeviceResolution",
    "GraphContext",
]
