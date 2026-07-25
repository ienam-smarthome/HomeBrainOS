from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .decision import RouteDecision
from .route import Route


class RouteRegistry:
    """Deterministic registry ordered by priority, then registration order."""

    def __init__(self, routes: Iterable[Route] | None = None) -> None:
        self._routes: list[tuple[int, Route]] = []
        self._sequence = 0

        for route in routes or ():
            self.register(route)

    def register(self, route: Route) -> Route:
        if not isinstance(route, Route):
            raise TypeError("route must be a Route instance")

        if not route.name.strip():
            raise ValueError("route name cannot be empty")

        if any(existing.name == route.name for _, existing in self._routes):
            raise ValueError(f'route "{route.name}" is already registered')

        self._routes.append((self._sequence, route))
        self._sequence += 1
        return route

    def unregister(self, name: str) -> bool:
        route_name = str(name or "").strip()
        original_count = len(self._routes)

        self._routes = [
            entry
            for entry in self._routes
            if entry[1].name != route_name
        ]

        return len(self._routes) != original_count

    def ordered_routes(self) -> tuple[Route, ...]:
        ordered = sorted(
            self._routes,
            key=lambda entry: (-entry[1].priority, entry[0]),
        )
        return tuple(route for _, route in ordered)

    def decide(
        self,
        query: str,
        context: Mapping[str, Any] | None = None,
    ) -> RouteDecision | None:
        considered: list[str] = []
        safe_context = context or {}

        for route in self.ordered_routes():
            considered.append(route.name)

            if route.matches(query, safe_context):
                return RouteDecision(
                    route_name=route.name,
                    priority=route.priority,
                    reason=route.reason,
                    considered_routes=tuple(considered),
                    metadata=route.metadata,
                )

        return None

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": route.name,
                "priority": route.priority,
                "reason": route.reason,
                "metadata": dict(route.metadata),
            }
            for route in self.ordered_routes()
        ]

    def __len__(self) -> int:
        return len(self._routes)
