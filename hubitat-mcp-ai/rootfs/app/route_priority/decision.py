from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Observable result of evaluating the route registry."""

    route_name: str
    priority: int
    reason: str
    considered_routes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_selected": self.route_name,
            "route_priority": self.priority,
            "route_reason": self.reason,
            "routes_considered": list(self.considered_routes),
            "route_metadata": dict(self.metadata),
        }
