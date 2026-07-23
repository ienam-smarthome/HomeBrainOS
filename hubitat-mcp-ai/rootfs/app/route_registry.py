from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


RouteMatcher = Callable[[str], bool]


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


@dataclass(frozen=True, slots=True)
class RouteMatch:
    name: str
    priority: int
    terminal: bool
    reason: str

    def response_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "priority": self.priority,
            "terminal": self.terminal,
            "reason": self.reason,
        }


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
        self._routes[route.name] = route

    def descriptors(self) -> tuple[RouteDescriptor, ...]:
        return tuple(
            sorted(self._routes.values(), key=lambda item: (-item.priority, item.name))
        )

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
                    )
                )
        selected = matches[0] if matches else None
        return RouteSelection(query=text, selected=selected, matches=tuple(matches))


__all__ = [
    "RouteDescriptor",
    "RouteMatch",
    "RouteRegistry",
    "RouteSelection",
]
