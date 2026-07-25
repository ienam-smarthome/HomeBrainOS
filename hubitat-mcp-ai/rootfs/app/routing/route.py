from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

RouteMatcher = Callable[[str, Mapping[str, Any]], bool]


@dataclass(frozen=True, slots=True)
class Route:
    """One named route with an explicit priority and deterministic matcher."""

    name: str
    priority: int
    matcher: RouteMatcher
    reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def matches(
        self,
        query: str,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        return bool(self.matcher(str(query or ""), context or {}))
