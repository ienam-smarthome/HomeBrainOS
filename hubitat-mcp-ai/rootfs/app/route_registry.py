from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Literal


RouteMatcher = Callable[[str], bool]
SafetyClass = Literal["read", "mutate", "destructive"]


@dataclass(frozen=True, slots=True)
class RouteDescriptor:
    """Metadata and matcher for one assistant route.

    The registry is intentionally side-effect free in 0.10.51. It records route
    precedence and produces diagnostics while existing handlers continue to
    execute through their proven wrappers. Later milestones can migrate handlers
    behind the same descriptors without changing priority semantics.
    """

    name: str
    priority: int
    terminal: bool
    matcher: RouteMatcher
    reason: str
    capability_id: str = ""
    mcp_tools: tuple[str, ...] = ()
    safety_class: SafetyClass = "read"
    slot_schema: tuple[tuple[str, str, bool], ...] = ()
    runtime_routes: tuple[str, ...] = ()
    runtime_intents: tuple[str, ...] = ()

    def response_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "priority": self.priority,
            "terminal": self.terminal,
            "reason": self.reason,
            "capability_id": self.capability_id or self.name,
            "mcp_tools": list(self.mcp_tools),
            "safety_class": self.safety_class,
            "slot_schema": [
                {"name": name, "type": type_name, "required": required}
                for name, type_name, required in self.slot_schema
            ],
            "runtime_routes": list(self.runtime_routes),
            "runtime_intents": list(self.runtime_intents),
        }


@dataclass(frozen=True, slots=True)
class RouteMatch:
    name: str
    priority: int
    terminal: bool
    reason: str
    capability_id: str
    mcp_tools: tuple[str, ...]
    safety_class: SafetyClass
    slot_schema: tuple[tuple[str, str, bool], ...]
    runtime_routes: tuple[str, ...]
    runtime_intents: tuple[str, ...]

    def response_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "priority": self.priority,
            "terminal": self.terminal,
            "reason": self.reason,
            "capability_id": self.capability_id,
            "mcp_tools": list(self.mcp_tools),
            "safety_class": self.safety_class,
            "slot_schema": [
                {"name": name, "type": type_name, "required": required}
                for name, type_name, required in self.slot_schema
            ],
            "runtime_routes": list(self.runtime_routes),
            "runtime_intents": list(self.runtime_intents),
        }

    def compare_answer(self, answer: dict[str, object]) -> bool | None:
        """Compare a conceptual match with runtime route/intent identifiers.

        ``None`` means the capability has not declared enough runtime aliases to
        make the comparison meaningful. This prevents the passive observer from
        counting conceptual names such as ``device-health`` as disagreements with
        implementation labels such as ``mcp-fast``.
        """

        expected_routes = set(self.runtime_routes)
        expected_intents = set(self.runtime_intents)
        if not expected_routes and not expected_intents:
            return None
        actual_route = str(answer.get("route") or "").strip()
        actual_intent = str(answer.get("intent") or "").strip()
        # Intent is normally more specific than broad implementation routes such
        # as ``mcp-fast``. Prefer it whenever both sides declare one.
        if expected_intents and actual_intent:
            return actual_intent in expected_intents
        if expected_routes and actual_route:
            return actual_route in expected_routes
        if not actual_route and not actual_intent:
            return None
        return False


@dataclass(frozen=True, slots=True)
class RouteSelection:
    query: str
    selected: RouteMatch | None
    matches: tuple[RouteMatch, ...]

    def response_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "selected": self.selected.response_dict() if self.selected else None,
            "matches": [match.response_dict() for match in self.matches],
        }


class RouteRegistry:
    """Explicit, deterministic route precedence catalogue.

    Routes are sorted by descending priority, then name for stable diagnostics.
    Duplicate names are rejected because silently replacing a route would make
    precedence dependent on import/install order again.
    """

    def __init__(self, routes: Iterable[RouteDescriptor] = ()) -> None:
        self._routes: dict[str, RouteDescriptor] = {}
        for route in routes:
            self.register(route)

    def register(self, route: RouteDescriptor) -> None:
        if route.name in self._routes:
            raise ValueError(f"Route already registered: {route.name}")
        if route.safety_class not in {"read", "mutate", "destructive"}:
            raise ValueError(
                f"Invalid safety class for {route.name}: {route.safety_class}"
            )
        self._routes[route.name] = route

    def descriptors(self) -> tuple[RouteDescriptor, ...]:
        return tuple(
            sorted(self._routes.values(), key=lambda item: (-item.priority, item.name))
        )

    def describe(self) -> list[dict[str, object]]:
        return [route.response_dict() for route in self.descriptors()]

    def select(self, query: str) -> RouteSelection:
        text = str(query or "").strip()
        matches: list[RouteMatch] = []
        for route in self.descriptors():
            try:
                matched = bool(route.matcher(text))
            except Exception:
                matched = False
            if matched:
                matches.append(
                    RouteMatch(
                        name=route.name,
                        priority=route.priority,
                        terminal=route.terminal,
                        reason=route.reason,
                        capability_id=route.capability_id or route.name,
                        mcp_tools=route.mcp_tools,
                        safety_class=route.safety_class,
                        slot_schema=route.slot_schema,
                        runtime_routes=route.runtime_routes,
                        runtime_intents=route.runtime_intents,
                    )
                )
        selected = matches[0] if matches else None
        return RouteSelection(query=text, selected=selected, matches=tuple(matches))


__all__ = [
    "RouteDescriptor",
    "RouteMatch",
    "RouteRegistry",
    "RouteSelection",
    "SafetyClass",
]
